from __future__ import annotations

import shlex
from dataclasses import dataclass

from cafe_order_kiosk.models import OrderStatus
from cafe_order_kiosk.kiosk_store import KioskStore
from cafe_order_kiosk.utils import format_money


@dataclass
class CLIState:
    current_order_id: int | None = None
    is_admin: bool = False # 관리자 권한 여부 (기본값: False)

def run_cli() -> int:
    store = KioskStore.with_default_menu()
    state = CLIState()

    print("카페 주문 키오스크")
    print("명령어 목록은 '도움말'을 입력하세요. 가격은 원 단위 정수입니다.")

    while True:
        try:
            raw = input("kiosk> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not raw:
            continue

        tokens = shlex.split(raw)
        command, args = tokens[0], tokens[1:]

        if command in {"종료", "끝", "quit", "exit"}:
            break
        elif command in {"도움말", "help"}:
            print_help()
        elif command in {"메뉴", "menu"}:
            handle_menu(store)
        elif command in {"주문", "order"}:
            handle_order(store, state, args)
        elif command in {"주문목록", "orders"}:
            handle_orders(store, args)
        elif command in {"결제", "pay"}:
            handle_pay(store, state, args)
        elif command in {"메뉴추가", "addmenu"}:
            if not chk_admin_perm(state):
                continue
            handle_add_menu(store, args)
        elif command in {"메뉴수정", "updatemenu"}:
            if not chk_admin_perm(state):
                continue
            handle_update_menu(store, args)
        elif command in {"메뉴삭제", "deletemenu"}:
            if not chk_admin_perm(state):
                continue
            handle_delete_menu(store, args)
        elif command in {"관리자", "admin"}:
            handle_admin(state)
        elif command in {"로그아웃", "logout"}:
            handle_admin_logout(state)
        else:
            print("알 수 없는 명령입니다. '도움말'을 입력하세요.")
    print("종료합니다.")
    return 0


def print_help() -> None:
    print("명령어:")
    print("\t메뉴")
    print("\t주문 생성 [메모]")
    print("\t주문 선택 <주문_id>")
    print("\t주문 추가 <메뉴_id> <수량> [옵션]")
    print("\t주문 삭제 <라인번호>")
    print("\t주문 조회")
    print("\t주문 취소")
    print("\t주문목록 목록 [진행중|결제완료|취소]")
    print("\t결제 <방법> [금액]")
    print("\t도움말")
    print("\t종료")
    print("\t메뉴 추가 <이름> <가격> [카테고리] [설명]")
    print("\t메뉴 수정 <메뉴_id> <이름> <가격> [카테고리] [설명] [품절여부:y/n]")
    print("\t메뉴 삭제 <메뉴_id>")
    print("\t관리자")
    print("\t로그아웃")


def handle_menu(store: KioskStore) -> None:
    print("메뉴:")
    for item in store.list_menu():
        description = f" - {item.description}" if item.description else ""
        print(
            f"\t{item.id}. {item.name} ({item.category}) - {format_money(item.price)}"
            f"{description}"
        )


def handle_order(store: KioskStore, state: CLIState, args: list[str]) -> None:
    if not args:
        print("주문 명령어: 생성, 선택, 추가, 삭제, 조회, 취소")
        return

    action, tail = args[0], args[1:]

    if action in {"생성", "new"}:
        note = " ".join(tail).strip() if tail else None
        order = store.create_order(note=note)
        state.current_order_id = order.id
        print(f"주문 #{order.id}가 생성되었습니다.")
    elif action in {"선택", "select"}:
        order_id = parse_int_arg(tail, "order_id")
        if order_id is None:
            return
        order = store.get_order(order_id)
        if order is None:
            print("주문을 찾을 수 없습니다.")
            return
        state.current_order_id = order.id
        print(f"주문 #{order.id}를 선택했습니다.")
    elif action in {"추가", "add"}:
        if state.current_order_id is None:
            print("선택된 주문이 없습니다. 먼저 '주문 생성'을 사용하세요.")
            return
        if len(tail) < 2:
            print("사용법: 주문 추가 <메뉴_id> <수량> [옵션]")
            return
        menu_id = parse_int_arg(tail[:1], "menu_id")
        quantity = parse_int_arg(tail[1:2], "qty")
        if menu_id is None or quantity is None:
            return

        options_text = " ".join(tail[2:]).strip()
        options = (
            [option.strip() for option in options_text.split(",") if option.strip()]
            if options_text
            else []
        )
        try:
            store.add_item(state.current_order_id, menu_id, quantity, options)
        except ValueError as exc:
            print(str(exc))
            return
        print("항목이 추가되었습니다.")
    elif action in {"삭제", "remove"}:
        if state.current_order_id is None:
            print("선택된 주문이 없습니다. 먼저 '주문 생성'을 사용하세요.")
            return
        line_index = parse_int_arg(tail, "line_index")
        if line_index is None:
            return
        try:
            store.remove_item(state.current_order_id, line_index)
        except ValueError as exc:
            print(str(exc))
            return
        print("항목이 삭제되었습니다.")
    elif action in {"조회", "show"}:
        if state.current_order_id is None:
            print("선택된 주문이 없습니다. 먼저 '주문 생성'을 사용하세요.")
            return
        order = store.get_order(state.current_order_id)
        if order is None:
            print("주문을 찾을 수 없습니다.")
            return
        print_order(order)
    elif action in {"취소", "cancel"}:
        if state.current_order_id is None:
            print("선택된 주문이 없습니다. 먼저 '주문 생성'을 사용하세요.")
            return
        try:
            order = store.cancel_order(state.current_order_id)
        except ValueError as exc:
            print(str(exc))
            return
        print(f"주문 #{order.id}가 취소되었습니다.")
    else:
        print("알 수 없는 주문 명령어입니다.")


def handle_orders(store: KioskStore, args: list[str]) -> None:
    if not args or args[0] not in {"list", "목록"}:
        print("사용법: 주문목록 목록 [진행중|결제완료|취소]")
        return

    status = None
    if len(args) > 1:
        status = parse_status(args[1])
        if status is None:
            return

    orders = store.list_orders(status)
    if not orders:
        print("주문이 없습니다.")
        return

    for order in orders:
        print(
            f"  #{order.id} {format_status(order.status)} - {format_money(order.total)}"
        )


def handle_pay(store: KioskStore, state: CLIState, args: list[str]) -> None:
    if state.current_order_id is None:
        print("선택된 주문이 없습니다. 먼저 '주문 생성'을 사용하세요.")
        return
    if not args:
        print("사용법: 결제 <방법> [금액]")
        return

    method = args[0]
    amount = None
    if len(args) > 1:
        amount = parse_int_arg(args[1:2], "amount")
        if amount is None:
            return

    order = store.get_order(state.current_order_id)
    if order is None:
        print("주문을 찾을 수 없습니다.")
        return
    if amount is None:
        amount = order.total

    try:
        store.pay_order(order.id, method, amount)
    except ValueError as exc:
        print(str(exc))
        return

    print(f"주문 #{order.id} 결제 완료 ({method}).")


def print_order(order) -> None:
    print(f"주문 #{order.id} ({format_status(order.status)})")
    if order.note:
        print(f"메모: {order.note}")
    if not order.items:
        print("  (비어 있음)")
        return

    for idx, item in enumerate(order.items, start=1):
        options = f" [{', '.join(item.options)}]" if item.options else ""
        print(
            f"  {idx}. {item.name}{options} x{item.quantity}"
            f" - {format_money(item.line_total)}"
        )
    print(f"합계: {format_money(order.total)}")


def parse_int_arg(args: list[str], name: str) -> int | None:
    if not args:
        print(f"필수 값이 없습니다: {name}")
        return None
    try:
        return int(args[0])
    except ValueError:
        print(f"잘못된 값: {name}")
        return None


def parse_status(raw: str) -> OrderStatus | None:
    normalized = raw.lower()
    status_map = {
        "open": OrderStatus.OPEN,
        "paid": OrderStatus.PAID,
        "canceled": OrderStatus.CANCELED,
        "진행중": OrderStatus.OPEN,
        "결제완료": OrderStatus.PAID,
        "취소": OrderStatus.CANCELED,
    }
    status = status_map.get(normalized)
    if status is None:
        print("잘못된 상태입니다. 진행중, 결제완료, 취소 중에서 선택하세요.")
    return status

def format_status(status: OrderStatus) -> str:
    status_map = {
        OrderStatus.OPEN: "진행중",
        OrderStatus.PAID: "결제완료",
        OrderStatus.CANCELED: "취소",
    }
    return status_map.get(status, status.value)

# 새 메뉴 추가
def handle_add_menu(store: KioskStore, args: list[str]) -> None:
    if len(args) < 2:
        print("사용법: 메뉴추가 <이름> <가격> [카테고리] [설명]")
        return

    name = args[0]
    try:
        price = int(args[1])
    except ValueError:
        print("가격은 정수여야 합니다.")
        return

    category = args[2] if len(args) > 2 else None
    description = args[3] if len(args) > 3 else None

    try:
        item = store.add_menu_item(name, price, category, description)
        print(f"메뉴가 성공적으로 추가되었습니다: [{item.id}] {item.name} - {format_money(item.price)}원")
    except ValueError as exc:
        print(str(exc))

# 기존 메뉴 수정 
def handle_update_menu(store: KioskStore, args: list[str]) -> None:
    if len(args) < 3:
        print("사용법: 메뉴수정 <메뉴_id> <이름> <가격> [카테고리] [설명] [품절여부:y/n]")
        return

    try:
        menu_id = int(args[0])
        price = int(args[2])
    except ValueError:
        print("메뉴 ID와 가격은 정수여야 합니다.")
        return

    name = args[1]
    category = args[3] if len(args) > 3 else None
    description = args[4] if len(args) > 4 else None
    
    # 품절 여부 수정
    is_available = True
    if len(args) > 5:
        is_available = args[5].lower() not in {"n", "no", "품절"}

    try:
        item = store.update_menu_item(menu_id, name, price, category, description, is_available)
        status_str = "판매중" if item.is_available else "품절"
        print(f"메뉴가 수정되었습니다: [{item.id}] {item.name} - {format_money(item.price)}원 ({status_str})")
    except ValueError as exc:
        print(str(exc))

# 기존 메뉴 삭제 
def handle_delete_menu(store: KioskStore, args: list[str]) -> None:
    if not args:
        print("사용법: 메뉴삭제 <메뉴_id>")
        return

    try:
        menu_id = int(args[0])
    except ValueError:
        print("메뉴 ID는 정수여야 합니다.")
        return

    try:
        store.delete_menu_item(menu_id)
        print(f"메뉴 ID {menu_id}가 삭제되었습니다.")
    except ValueError as exc:
        print(str(exc))


ADMIN_PASSWORD = "q1w2e3r4"

# 관리자 모드로 전환
def handle_admin(state: CLIState) -> None:
    if state.is_admin:
        print("이미 관리자 모드입니다.")
        return
    password = input("관리자 비밀번호를 입력하세요: ")
    if password == ADMIN_PASSWORD:
        state.is_admin = True
        print("관리자 모드로 전환되었습니다.")
    else:
        print("비밀번호가 일치하지 않습니다.")

# 관리자 권한 종료
def handle_admin_logout(state: CLIState) -> None:
    if not state.is_admin:
        print("현재 관리자 모드가 아닙니다.")
        return
    state.is_admin = False
    print("관리자 모드에서 로그아웃 하였습니다.")

# 관리자 권한 체크
def chk_admin_perm(state: CLIState) -> bool:
    if not state.is_admin:
        print("권한이 없습니다. '관리자' 명령어를 통해 관리자 모드로 전환해주세요")
        return False
    return True