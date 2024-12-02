from __future__ import annotations
# import sys
from typing import Any, Optional, List, Dict
from pydantic import BaseModel, ConfigDict
from flet import View
from renderer import Renderer
import secrets
import inspect
import importlib.util


class PageLoader(BaseModel):
    model_config = ConfigDict(strict=False, arbitrary_types_allowed=True)
    name: str
    uri: str
    session_data: Dict[str, Any] = {}
    renderer: Renderer
    _page_object: Optional[Any] = None

    def build(self: PageLoader) -> None:
        # Load module
        spec = importlib.util.spec_from_file_location(self.name, self.uri)
        module = importlib.util.module_from_spec(spec)
        # sys.modules[self.name] = module
        spec.loader.exec_module(module)
        objects = []
        # Get relevant objects
        object_names = filter(
            lambda name: (
                not name.startswith("__")
                and "__module__" in dir(getattr(module, name))
                and getattr(module, name).__module__ == self.name
            ),
            dir(module),
        )
        # Save just views or wrappers with class attribute 'is_page'
        for obj_name in object_names:
            obj = getattr(module, obj_name)
            if isinstance(obj, View):
                objects.append(obj)
            elif inspect.isclass(obj) and View in obj.__bases__:
                objects.append(obj)
            elif inspect.isclass(obj) and "_is_page" in dir(obj) and obj._is_page:
                objects.append(obj)
            else:
                pass

        # No objects found
        if len(objects) == 0:
            raise IOError(
                f"No page view defined on '{self.uri}'. "
                "Make sure wrapping classes have the class "
                "attribute _is_page = True"
            )
        else:    
            if len(objects) > 1:
                print(
                    f"Multiple page views defined on {self.uri}. "
                    "Using the first object found."
                )
            page_object = objects[0]
            if inspect.isclass(page_object):
                self._page_object = page_object(session_data=self.session_data)
            else:
                self._page_object = page_object
            print(f"Object {self._page_object} built.")
            if "set" in dir(page_object):
                self._page_object.set(self.renderer)

    def update(self: PageLoader, session_data: Dict[str, Any]) -> None:
        self.session_data.update(session_data)
        # NOTE: this method must be implemented
        self._page_object.update_session_data(session_data)

    def show(self: PageLoader) -> None:
        if self._page_object is None:
            self.build()
        if isinstance(self._page_object, View):
            page = self._page_object
        else:
            for attr_name in filter(lambda name: not name.startswith("__"), dir(self._page_object)):
                attribute = getattr(self._page_object, attr_name)
                if isinstance(attribute, View):
                    page = attribute
                    break
        self.renderer.show(page)


class GuiList(BaseModel):
    model_config = ConfigDict(strict=False, arbitrary_types_allowed=True)
    namespace: Optional[str]
    renderer: Renderer
    _pages: List[PageLoader] = []

    def insert(
        self: GuiList,
        position: int,
        values: List[Dict[str, str]],
        session_data: Dict[str, Any],
    ) -> None:
        position = min(position, len(self._pages))
        prefix = self.namespace.replace('.', '_')
        for item in reversed(values):
            token = secrets.token_hex(4)
            self._pages.insert(
                position,
                PageLoader(
                    name=item.get("page", f"{prefix}_{token}"),
                    uri=item.get("url"),
                    session_data=session_data,
                    renderer=self.renderer,
                )
            )

    def move(
        self: GuiList,
        from_pos: int,
        to_pos: int,
        items_number: int = 1,
    ) -> None:
        from_pos = min(from_pos, len(self._pages) - 1)
        to_pos = min(to_pos, len(self._pages))
        for _ in range(items_number):
            item = self._pages.pop(from_pos)
            self._pages.insert(to_pos + 1, item)

    def remove(
        self: GuiList,
        position: int,
        items_number: int = 1,
    ) -> None:
        position = min(position, len(self._pages))
        for _ in range(items_number):
            if position < len(self._pages):
                del self._pages[position]

    def show(
        self: GuiList,
        position: int,
    ) -> None:
        if 0 <= position < len(self._pages):
            self._pages[position].show()