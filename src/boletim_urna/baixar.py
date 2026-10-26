"""Download com cache: um arquivo já baixado nunca é baixado de novo."""

import logging
from pathlib import Path

import httpx

from . import fontes

log = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(60.0, read=300.0)


def baixar_arquivo(url: str, destino: Path, forcar: bool = False) -> Path:
    """Baixa `url` para `destino` via arquivo temporário (.part), para não deixar downloads pela metade."""
    if destino.exists() and not forcar:
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_suffix(destino.suffix + ".part")
    log.info("baixando %s", url)
    with httpx.stream("GET", url, timeout=TIMEOUT, follow_redirects=True) as resp:
        resp.raise_for_status()
        with parcial.open("wb") as f:
            for bloco in resp.iter_bytes(1 << 20):
                f.write(bloco)
    parcial.replace(destino)
    return destino


def baixar_munzona(anos=fontes.ANOS, forcar: bool = False) -> list[Path]:
    caminhos = []
    for ano in anos:
        for dataset in fontes.DATASETS_MUNZONA:
            caminhos.append(
                baixar_arquivo(fontes.url_odsele(dataset, ano), fontes.caminho_bruto(dataset, ano), forcar)
            )
    return caminhos
