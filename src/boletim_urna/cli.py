"""Linha de comando: `boletim-urna baixar | processar | atualizar`."""

import logging
import zipfile

import typer

from . import baixar as _baixar
from . import comparacao, df_ra, fontes, processar as _processar, unidades

app = typer.Typer(help="Pipeline de resultados eleitorais 2022 × 2026 (TSE).", no_args_is_help=True)


@app.callback()
def _config(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    logging.basicConfig(level=logging.INFO if verbose else logging.WARNING, format="%(asctime)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)


@app.command()
def baixar(forcar: bool = typer.Option(False, help="Baixa de novo mesmo se já existir.")) -> None:
    """Baixa os arquivos do TSE Dados Abertos (município/zona; seção e locais para o DF)."""
    for caminho in [*_baixar.baixar_munzona(forcar=forcar), *_baixar.baixar_secao(forcar=forcar)]:
        typer.echo(caminho.relative_to(fontes.RAIZ))


@app.command()
def processar() -> None:
    """Gera os Parquets em data/processed/ (completa o 2º turno de 2026 pela API se faltar no CSV)."""
    _processar.processar()
    df_ra.processar()
    unidades.processar()
    comparacao.processar()
    typer.echo("ok")


def _csv_2026_tem_2o_turno() -> bool:
    caminho = fontes.caminho_bruto("detalhe_votacao_munzona", 2026)
    with zipfile.ZipFile(caminho) as z, z.open("detalhe_votacao_munzona_2026_BR.csv") as f:
        cabecalho = f.readline().decode("latin-1").replace('"', "").strip().split(";")
        i = cabecalho.index("NR_TURNO")
        return any(linha.decode("latin-1").replace('"', "").split(";")[i] == "2" for linha in f)


def _conferir_bu() -> None:
    """Conferência seção a seção: BUs decodificados × CSV oficial do 2º turno de 2026 no DF."""
    import duckdb

    from . import bu

    con = duckdb.connect()
    partes = [
        f"SELECT * FROM {df_ra._csv(df_ra._extrair(chave, 2026, nome))} WHERE SG_UF = 'DF' AND NR_TURNO = '2'"
        for chave, nome in (("votacao_secao_df", "votacao_secao_2026_DF.csv"), ("votacao_secao_br", "votacao_secao_2026_BR.csv"))
    ]
    csv = con.sql(f"""
        SELECT NR_ZONA::INT AS nr_zona, NR_SECAO::INT AS nr_secao, CD_CARGO::INT AS cd_cargo,
               NR_VOTAVEL::INT AS nr_votavel, QT_VOTOS::BIGINT AS qt_votos
        FROM ({" UNION ALL ".join(partes)})
    """).df()
    divergencias = bu.conferir_com_csv(csv)
    destino = fontes.PROCESSADOS / "conferencia_bu_csv_df_2t_2026.csv"
    divergencias.to_csv(destino, index=False)
    if divergencias.empty:
        typer.echo("Conferência BU × CSV: todas as seções do DF conferem.")
    else:
        typer.echo(f"Conferência BU × CSV: {len(divergencias)} divergência(s) — ver {destino.name}")


@app.command()
def atualizar() -> None:
    """Verifica se o TSE já publicou o 2º turno de 2026 em CSV; se sim, rebaixa e reprocessa."""
    _baixar.baixar_arquivo(
        fontes.url_odsele("detalhe_votacao_munzona", 2026),
        fontes.caminho_bruto("detalhe_votacao_munzona", 2026),
        forcar=True,
    )
    if not _csv_2026_tem_2o_turno():
        typer.echo("O CSV oficial de 2026 ainda não tem o 2º turno; mantendo dados da API.")
        return
    typer.echo("2º turno publicado em CSV: rebaixando e reprocessando.")
    _baixar.baixar_munzona(anos=(2026,), forcar=True)
    _baixar.baixar_secao(anos=(2026,), forcar=True)
    for csv in list(_processar.TEMP.glob("*2026_BRASIL.csv")) + list(_processar.TEMP.glob("*2026_D*.csv")) + list(
        _processar.TEMP.glob("*2026_BR.csv")
    ):
        csv.unlink()
    _conferir_bu()
    _processar.processar()
    df_ra.processar()
    unidades.processar()
    comparacao.processar()
    typer.echo("ok — rode `uv run pytest` para conferir os totais.")


@app.command()
def comparar() -> None:
    """Gera a comparação 2022 × 2026 de Presidente (data/processed/comparacao_presidente.parquet)."""
    comparacao.processar()
    typer.echo("ok")


@app.command()
def painel() -> None:
    """Abre o painel Streamlit."""
    import subprocess
    import sys

    subprocess.run([sys.executable, "-m", "streamlit", "run", str(fontes.RAIZ / "app" / "painel.py")], check=False)
