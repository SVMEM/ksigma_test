from aiogram.filters.callback_data import CallbackData

class MenuCB(CallbackData, prefix="menu"):
    action: str

# ===== ADMIN =====
class AdminCB(CallbackData, prefix="adm"):
    action: str
    id: int | None = None
    page: int | None = None


# ===== SOLVE =====
class SolveCB(CallbackData, prefix="sol"):
    action: str
    id: int | None = None
    page: int | None = None


class OptionCB(CallbackData, prefix="opt"):
    qid: int
    oid: int