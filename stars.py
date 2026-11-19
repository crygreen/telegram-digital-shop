import re


def star_order_id(payload):
    match = re.fullmatch(r"star:([a-f0-9]{32})", payload or "")
    return match[1] if match else None


async def send_delivery(bot, user_id, kind, file_id, caption):
    if kind == "video_note":
        await bot.send_video_note(user_id, video_note=file_id, protect_content=True)
        return
    methods = {
        "photo": "send_photo",
        "video": "send_video",
        "document": "send_document",
    }
    send = getattr(bot, methods[kind])
    await send(user_id, **{kind: file_id}, caption=caption, protect_content=True)
