"""Registro dos mundos simulados."""

from toolbr.worlds.atendimento import AtendimentoWorld
from toolbr.worlds.banco import BancoWorld
from toolbr.worlds.base import NOW, NOW_LABEL, ToolSpec, World
from toolbr.worlds.delivery import DeliveryWorld

WORLDS: dict[str, type[World]] = {
    "delivery": DeliveryWorld,
    "banco": BancoWorld,
    "atendimento": AtendimentoWorld,
}


def make_world(name: str, **kwargs) -> World:
    if name not in WORLDS:
        raise ValueError(f"mundo desconhecido: {name}. Opções: {', '.join(WORLDS)}")
    return WORLDS[name](**kwargs)


__all__ = ["NOW", "NOW_LABEL", "WORLDS", "ToolSpec", "World", "make_world"]
