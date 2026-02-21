from app.vk.keyboards import main_menu_keyboard


async def handle_vk_message(container, peer_id: int, user_id: int, text: str):

    if text.lower() in ("/start", "начать", "старт"):
        return {
            "text": "Добро пожаловать! Выберите действие:",
            "keyboard": main_menu_keyboard(),
        }

    result = await container.requests_service.handle_text(
        peer_id=peer_id,
        user_id=user_id,
        text=text,
        transport="vk",
    )

    if not result:
        return None

    return {
        "text": getattr(result, "text", str(result)),
        "keyboard": None,
    }