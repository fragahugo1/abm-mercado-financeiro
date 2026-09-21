from decimal import Decimal

from mercadolab.api.ativo import Ativo, TipoAtivo

from .agents import AgenteChartista, AgenteFundamentalista
from .simulation import ConfiguracaoSimulacao, SimulacaoMercadoArtificial


def criar_simulacao() -> SimulacaoMercadoArtificial:
    # Este bloco concentra os parâmetros que podem ser alterados no experimento.
    ativo = Ativo(
        ticker="ACAO",
        tipo=TipoAtivo.ACAO,
        nome="Acao Artificial",
        moeda="BRL",
    )
    agentes = [
        AgenteFundamentalista(
            id=0,
            nome="Agente Fundamentalista",
            saldo=Decimal("10000.00"),
            valor_fundamental=Decimal("40.00"),
            quantidade_ativo=1000,
            custo_informacao=Decimal("0.25"),
        ),
        AgenteChartista(
            id=1,
            nome="Agente Chartista",
            saldo=Decimal("10000.00"),
            quantidade_ativo=1000,
        ),
    ]
    return SimulacaoMercadoArtificial(
        ativo=ativo,
        preco_inicial=Decimal("42.00"),
        agentes=agentes,
        configuracao=ConfiguracaoSimulacao(quantidade_ticks=20, semente=42),
    )


def main() -> None:
    simulacao = criar_simulacao()
    for _ in range(simulacao.configuracao.quantidade_ticks):
        tick = simulacao.simulacao.tempo_atual.tick
        transacoes = simulacao.executar_tick()
        print(simulacao.resumo_tick(tick, transacoes))
        print()


if __name__ == "__main__":
    main()