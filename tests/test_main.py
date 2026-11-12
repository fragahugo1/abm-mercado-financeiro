import sys
from decimal import Decimal
from math import log, sqrt

import matplotlib.pyplot as plt
import pytest

from abm_mercado_financeiro import main
from abm_mercado_financeiro.agents import (
    AgenteChartista,
    AgenteFundamentalista,
    AgenteRuidoso,
)


@pytest.mark.parametrize(
    ("p", "total", "esperado"),
    [(1, 100, (1, 99)), (20, 100, (20, 80)), (99, 100, (99, 1)),
     (22, 20, (4, 16)), (25, 10, (3, 7))],
)
def test_calcular_quantidades(p: int, total: int, esperado: tuple[int, int], monkeypatch) -> None:
    monkeypatch.setattr(main, "QUANTIDADE_AGENTES", total)
    assert main.calcular_quantidades(p) == esperado


@pytest.mark.parametrize(
    ("p", "total"),
    [(-1, 100), (0, 100), (100, 100), (101, 100), (1, 20), (99, 20), (50, 1)],
)
def test_calcular_quantidades_rejeita_configuracoes_invalidas(p: int, total: int, monkeypatch) -> None:
    monkeypatch.setattr(main, "QUANTIDADE_AGENTES", total)
    with pytest.raises(ValueError):
        main.calcular_quantidades(p)


def test_criar_simulacao_usa_percentuais_de_fundamentalistas_e_ruidosos() -> None:
    simulacao = main.criar_simulacao(20, 10)

    assert len(simulacao.agentes) == 120
    assert sum(isinstance(a, AgenteFundamentalista) for a in simulacao.agentes) == 24
    assert sum(isinstance(a, AgenteRuidoso) for a in simulacao.agentes) == 12
    assert sum(isinstance(a, AgenteChartista) for a in simulacao.agentes) == 84


@pytest.mark.parametrize(
    ("p", "p_ruido", "esperado"),
    [(36, 33, (43, 37, 40)), (1, 0, (1, 119, 0)), (99, 0, (119, 1, 0))],
)
def test_calcular_composicao(p, p_ruido, esperado) -> None:
    assert main.calcular_composicao(p, p_ruido) == esperado


@pytest.mark.parametrize(("p", "p_ruido"), [(0, 0), (100, 0), (50, 100), (50, 60)])
def test_calcular_composicao_rejeita_percentuais_invalidos(p, p_ruido) -> None:
    with pytest.raises(ValueError):
        main.calcular_composicao(p, p_ruido)


def test_criar_simulacao_usa_validade_configurada(monkeypatch) -> None:
    monkeypatch.setattr(main, "VALIDADE_ORDEM_TICKS", 7)
    assert main.criar_simulacao(20).configuracao.validade_ordem_ticks == 7


def test_imprimir_series_inclui_preco_inicial_e_variacoes(capsys) -> None:
    precos = [Decimal("4.10"), Decimal("4.15"), Decimal("4.12")]

    main.imprimir_series(precos)

    linhas = [[coluna.strip() for coluna in linha.split("|")] for linha in capsys.readouterr().out.splitlines()]
    assert linhas == [
        ["Tick", "Preço", "Variação"],
        ["Inicial", "4.10", "-"],
        ["0", "4.15", "+0.05"],
        ["1", "4.12", "-0.03"],
    ]


def test_estatisticas_dos_retornos_logaritmicos() -> None:
    precos = list(map(Decimal, ["1", "1", "1", "1", "2"]))
    media, variancia, assimetria, curtose = main.calcular_estatisticas_retornos(precos)
    assert media == pytest.approx(log(2) / 4)
    assert variancia == pytest.approx(3 * log(2) ** 2 / 16)
    assert assimetria == pytest.approx(2 / sqrt(3))
    assert curtose == pytest.approx(7 / 3)


def test_estatisticas_sem_variacao(capsys) -> None:
    precos = [Decimal("4.10")] * 3
    assert main.calcular_estatisticas_retornos(precos) == (0.0, 0.0, None, None)
    main.imprimir_estatisticas(precos)
    assert "Assimetria: indefinida (variância zero)" in capsys.readouterr().out


@pytest.mark.parametrize(
    "precos",
    [[], [Decimal("1")], [Decimal("1"), Decimal("0")], [Decimal("1"), Decimal("NaN")]],
)
def test_estatisticas_rejeitam_precos_invalidos(precos) -> None:
    with pytest.raises(ValueError):
        main.calcular_estatisticas_retornos(precos)


@pytest.mark.parametrize(
    "argumentos",
    [
        [],
        ["--p", "0", "--p-ruido", "0"],
        ["--p", "100", "--p-ruido", "0"],
        ["--p", "2.5", "--p-ruido", "0"],
        ["--p", "20"],
    ],
)
def test_main_rejeita_p_ausente_ou_invalido(argumentos, monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["abm-mercado-financeiro", *argumentos])
    with pytest.raises(SystemExit) as erro:
        main.main()
    assert erro.value.code == 2
    assert "error:" in capsys.readouterr().err


def test_main_imprime_series_e_mostra_grafico_de_precos(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["abm-mercado-financeiro", "--p", "20", "--p-ruido", "10"]
    )
    monkeypatch.setattr(main, "QUANTIDADE_TICKS", 3)
    graficos = []
    monkeypatch.setattr(plt, "show", lambda: graficos.append(plt.gcf()))

    main.main()

    saida = capsys.readouterr().out
    assert "24 fundamentalistas" in saida
    assert "12 ruidosos" in saida
    assert "84 chartistas" in saida
    assert "TICK " not in saida
    partes = saida.splitlines()
    linhas = [[coluna.strip() for coluna in linha.split("|")] for linha in partes[1:6]]
    assert linhas[0] == ["Tick", "Preço", "Variação"]
    assert linhas[1] == ["Inicial", f"{main.PRECO_INICIAL:.2f}", "-"]
    assert len(linhas) == 5
    for indice, (anterior, atual) in enumerate(zip(linhas[1:], linhas[2:])):
        assert int(atual[0]) == indice
        assert Decimal(atual[2]) == Decimal(atual[1]) - Decimal(anterior[1])
    assert "Estatísticas dos retornos logarítmicos:" in saida
    assert "Variância:" in saida
    assert "Curtose:" in saida
    assert list(tmp_path.iterdir()) == []
    assert len(graficos) == 1
    assert len(graficos[0].axes) == 1
    assert len(graficos[0].axes[0].lines[0].get_ydata()) == 4
    assert list(graficos[0].axes[0].lines[0].get_xdata()) == [-1, 0, 1, 2]
    plt.close(graficos[0])
