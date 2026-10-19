from decimal import Decimal
from random import Random

from abm_mercado_financeiro.agents import AgenteChartista, AgenteFundamentalista
from abm_mercado_financeiro.main import criar_agentes
from abm_mercado_financeiro.simulation import ConfiguracaoSimulacao, SimulacaoMercadoArtificial
from mercadolab.api.ativo import Ativo, TipoAtivo
from mercadolab.api.tempo import Tempo


def criar_simulacao(semente: int = 42) -> SimulacaoMercadoArtificial:
    ativo = Ativo(ticker="TEST", tipo=TipoAtivo.ACAO)
    agentes = [
        AgenteFundamentalista(0, "Fundamentalista", Decimal("100"), Decimal("40"), 5),
        AgenteChartista(1, "Chartista", Decimal("100"), 5),
    ]
    return SimulacaoMercadoArtificial(
        ativo, Decimal("42"), agentes, ConfiguracaoSimulacao(10, semente)
    )


def test_simulacao_preserva_saldo_total_e_ids() -> None:
    simulacao = criar_simulacao()
    saldo_inicial = sum(agente.saldo for agente in simulacao.agentes)
    saldos_iniciais = [agente.saldo for agente in simulacao.agentes]

    resultados = simulacao.executar()

    assert sum(agente.saldo for agente in simulacao.agentes) == saldo_inicial
    assert [agente.id for agente in simulacao.agentes] == [0, 1]
    assert all(agente.saldo >= 0 for agente in simulacao.agentes)
    assert any(transacoes for _, transacoes in resultados)
    assert simulacao.historico_precos[0] != simulacao.historico_precos[1]
    assert [agente.saldo for agente in simulacao.agentes] != saldos_iniciais


def test_mesma_semente_reproduz_precos() -> None:
    primeira = criar_simulacao(42)
    segunda = criar_simulacao(42)

    primeira.executar()
    segunda.executar()

    assert primeira.historico_precos == segunda.historico_precos


def test_fabrica_cria_quantidades_configuradas_com_ids_unicos() -> None:
    agentes = criar_agentes(quantidade_fundamentalistas=3, quantidade_chartistas=2)

    assert len(agentes) == 5
    assert [agente.id for agente in agentes] == [0, 1, 2, 3, 4]
    assert sum(isinstance(agente, AgenteFundamentalista) for agente in agentes) == 3
    assert sum(isinstance(agente, AgenteChartista) for agente in agentes) == 2


def test_populacao_tem_parametros_heterogeneos_e_negocia() -> None:
    agentes = criar_agentes(quantidade_fundamentalistas=10, quantidade_chartistas=10)
    fundamentalistas = [a for a in agentes if isinstance(a, AgenteFundamentalista)]
    chartistas = [a for a in agentes if isinstance(a, AgenteChartista)]
    ativo = Ativo(ticker="POP", tipo=TipoAtivo.ACAO)
    simulacao = SimulacaoMercadoArtificial(
        ativo,
        Decimal("4.50"),
        agentes,
        ConfiguracaoSimulacao(5, 42),
    )

    assert len({a.saldo for a in agentes}) > 1
    assert len({a.quantidade_ativo for a in agentes}) > 1
    assert len({a.valor_fundamental for a in fundamentalistas}) > 1
    assert len({a.janela for a in chartistas}) > 1
    assert any(transacoes for _, transacoes in simulacao.executar())


def test_resumo_separa_agentes_por_estrategia() -> None:
    simulacao = criar_simulacao()

    resumo = simulacao.resumo_tick(2)

    assert "TICK 2" in resumo
    assert "FUNDAMENTALISTAS (1)" in resumo
    assert "CHARTISTAS (1)" in resumo
    assert resumo.index("FUNDAMENTALISTAS") < resumo.index("CHARTISTAS")


def test_ordem_respeita_quantidade_maxima_e_ajuste_configurados() -> None:
    agente = AgenteFundamentalista(
        0,
        "Fundamentalista",
        Decimal("100"),
        Decimal("40"),
        ajuste_preco_limite=Decimal("0.05"),
        quantidade_maxima_ordem=2,
    )
    ativo = Ativo(ticker="CFG", tipo=TipoAtivo.ACAO)

    ordem = agente.gerar_ordem(
        ativo, Tempo(tick=0), Decimal("4.00"), [Decimal("4.00")], Random(1)
    )

    assert ordem is not None
    assert ordem.quantidade == 2
    assert ordem.preco_limite == Decimal("4.05")