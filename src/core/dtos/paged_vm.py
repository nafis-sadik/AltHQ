from typing import TypeVar, Generic, Sequence, Optional

T = TypeVar('T')

class PagedModel(Generic[T]):
    def __init__(
        self,
        search_string: Optional[str] = None,
        sort_by: Optional[str] = None,
        source_data: Optional[Sequence[T]] = None,
        page_number: int = 1,
        page_length: int = 10,
        total_items: int = 0,
        has_create_access: bool = False,
        has_update_access: bool = False,
        has_delete_access: bool = False
    ):
        self.search_string: Optional[str] = search_string
        self.sort_by: Optional[str] = sort_by
        self.source_data: Optional[Sequence[T]] = source_data
        
        # Internal private backings for properties
        self._page_number: int = 0
        self._page_length: int = 10
        
        # Trigger setters to apply logic validation
        self.page_number = page_number
        self.page_length = page_length
        
        self.total_items: int = total_items
        self.has_create_access: bool = has_create_access
        self.has_update_access: bool = has_update_access
        self.has_delete_access: bool = has_delete_access

    # PageNumber Getter and Setter
    @property
    def page_number(self) -> int:
        return self._page_number

    @page_number.setter
    def page_number(self, value: int) -> None:
        self._page_number = 0 if value <= 0 else value

    # PageLength Getter and Setter
    @property
    def page_length(self) -> int:
        return self._page_length

    @page_length.setter
    def page_length(self, value: int) -> None:
        self._page_length = 10 if value <= 0 else value

    # Computed Skip Property (Read-Only)
    @property
    def skip(self) -> int:
        # Note: If page_number can be 0, we clamp to max(0, page_number - 1) 
        # to prevent negative skip intervals.
        adjusted_page = max(0, self._page_number - 1)
        return self._page_length * adjusted_page
