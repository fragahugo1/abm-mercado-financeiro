from decimal import Decimal

from abm_mercado_financeiro.agents import AgenteChartista, AgenteFundamentalista
from abm_mercado_financeiro.simulation import ConfiguracaoSimulacao, SimulacaoMercadoArtificial
from mercadolab.api.ativo import Ativo, TipoAtivo


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