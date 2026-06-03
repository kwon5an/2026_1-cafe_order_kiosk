from __future__ import annotations

from collections.abc import Iterable

from cafe_order_kiosk.models import MenuItem, Order, OrderItem, OrderStatus, Payment
from cafe_order_kiosk.utils import utc_now

DEFAULT_MENU: tuple[MenuItem, ...] = (
    MenuItem(id=1, name="Americano", price=3500, category="coffee"),
    MenuItem(id=2, name="Latte", price=4000, category="coffee"),
    MenuItem(id=3, name="Cappuccino", price=4200, category="coffee"),
    MenuItem(id=4, name="Cold Brew", price=4500, category="coffee"),
    MenuItem(id=5, name="Matcha Latte", price=4800, category="tea"),
    MenuItem(id=6, name="Chamomile Tea", price=3800, category="tea"),
    MenuItem(id=7, name="Lemonade", price=4200, category="juice"),
    MenuItem(id=8, name="Butter Croissant", price=3500, category="bakery"),
    MenuItem(id=9, name="Blueberry Muffin", price=3200, category="bakery"),
    MenuItem(id=10, name="Cheesecake", price=5200, category="dessert"),
)


class KioskStore:
    def __init__(self, menu_items: Iterable[MenuItem] | None = None) -> None:
        self._menu: dict[int, MenuItem] = {item.id: item for item in (menu_items or [])}
        self._orders: dict[int, Order] = {}
        self._next_order_id = 1

    @classmethod
    def with_default_menu(cls) -> KioskStore:
        return cls(menu_items=DEFAULT_MENU)

    def list_menu(self, only_available: bool = True) -> list[MenuItem]:
        items: Iterable[MenuItem] = self._menu.values()
        if only_available:
            items = [item for item in items if item.is_available]
        return sorted(items, key=lambda item: item.id)

    def get_menu_item(self, menu_item_id: int) -> MenuItem | None:
        return self._menu.get(menu_item_id)

    def create_order(self, note: str | None = None) -> Order:
        order_id = self._next_order_id
        self._next_order_id += 1

        order = Order(id=order_id, note=note)
        self._orders[order_id] = order
        return order

    def list_orders(self, status: OrderStatus | None = None) -> list[Order]:
        orders: Iterable[Order] = self._orders.values()
        if status is not None:
            orders = [order for order in orders if order.status == status]
        return sorted(orders, key=lambda order: order.id)

    def get_order(self, order_id: int) -> Order | None:
        return self._orders.get(order_id)

    def add_item(
        self,
        order_id: int,
        menu_item_id: int,
        quantity: int,
        options: list[str] | None = None,
    ) -> Order:
        order = self._require_order(order_id)
        if order.status is not OrderStatus.OPEN:
            raise ValueError("Order is not open")
        if quantity < 1:
            raise ValueError("Quantity must be at least 1")

        menu_item = self._menu.get(menu_item_id)
        if menu_item is None:
            raise ValueError("Menu item not found")
        if not menu_item.is_available:
            raise ValueError("Menu item is not available")
        
        order_item = OrderItem(
            menu_item_id=menu_item.id,
            name=menu_item.name,
            unit_price=menu_item.price,
            quantity=quantity,
            options=options or [],
        )
        order.items.append(order_item)
        return order

    def remove_item(self, order_id: int, line_index: int) -> Order:
        order = self._require_order(order_id)
        if order.status is not OrderStatus.OPEN:
            raise ValueError("Order is not open")
        if line_index < 1 or line_index > len(order.items):
            raise ValueError("Line item not found")

        order.items.pop(line_index - 1)
        return order

    def cancel_order(self, order_id: int) -> Order:
        order = self._require_order(order_id)
        if order.status is OrderStatus.CANCELED:
            return order
        if order.status is OrderStatus.PAID:
            raise ValueError("Paid order cannot be canceled")

        order.status = OrderStatus.CANCELED
        order.canceled_at = utc_now()
        return order

    def pay_order(self, order_id: int, method: str, amount: int) -> Order:
        order = self._require_order(order_id)
        if order.status is not OrderStatus.OPEN:
            raise ValueError("Order is not open")
        if not order.items:
            raise ValueError("Order has no items")
        if amount != order.total:
            raise ValueError("Payment amount does not match total")

        order.status = OrderStatus.PAID
        order.paid_at = utc_now()
        order.payment = Payment(method=method, amount=amount, paid_at=order.paid_at)
        return order

    def _require_order(self, order_id: int) -> Order:
        order = self._orders.get(order_id)
        if order is None:
            raise ValueError("Order not found")
        return order
    
    # 새 메뉴 추가
    def add_menu_item(self, name: str, price: int, category: str | None = None, description: str | None = None) -> MenuItem:
        if price < 0:
            raise ValueError("가격은 0원 이상이어야 합니다.")
        
        next_id = max(self._menu.keys(), default=0) + 1

        item = MenuItem(
            id=next_id,
            name=name,
            price=price,
            category=category,
            description=description,
        )
        self._menu[next_id] = item
        return item
    
    # 메뉴 수정
    def update_menu_item(self, menu_id: int, name: str, price: int, category: str | None = None, description: str | None = None, is_available: bool = True) -> MenuItem:
        if menu_id not in self._menu:
            raise ValueError(f"메뉴 {menu_id}을(를) 찾을 수 없습니다.")
        if price < 0:
            raise ValueError("가격은 0원 이상이어야 합니다.")
        # MenuItem이 frozen=True 설정되어 있으므로, 객체 새로 생성 후 덮어쓰기
        updated_item = MenuItem(
            id=menu_id,
            name=name,
            price=price,
            category=category,
            description=description,
            is_available=is_available,
        )
        self._menu[menu_id] = updated_item
        return updated_item
    
    # 메뉴 삭제
    def delete_menu_item(self, menu_id: int) -> None:
        if menu_id not in self._menu:
            raise ValueError(f"메뉴 {menu_id}을(를) 찾을 수 없습니다.")
        del self._menu[menu_id]