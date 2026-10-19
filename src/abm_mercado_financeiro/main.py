from decimal import Decimal
from random import Random

import matplotlib.pyplot as plt
from mercadolab.api.ativo import Ativo, TipoAtivo

from .agents import AgenteChartista, AgenteFundamentalista
from .simulation import ConfiguracaoSimulacao, SimulacaoMercadoArtificial

# ===== Configurações Gerais - Constantes Flexíveis =====

# ===== Simulação =====
QUANTIDADE_TICKS = 500  # quantos ticks (rodadas de negociação) a simulação executa
SEMENTE_POPULACAO = 30  # reproduz o sorteio dos agentes (saldo, ações, parâmetros)
SEMENTE_SIMULACAO = 50  # reproduz os sorteios durante os ticks (decisões e ordem das ordens)

# ===== Saída =====
IMPRIMIR_A_CADA_N_TICKS = 1  # mínimo 1; 1 imprime todo tick, 10 imprime um a cada 10
MOSTRAR_GRAFICO = True  # abre o gráfico de preços ao final

# ===== Ativo =====
TICKER = "ACAO"  # código do ativo no mercado
NOME_ATIVO = "Acao Artificial"  # nome descritivo do ativo
MOEDA = "BRL"  # moeda de negociação
TICK_SIZE = Decimal("0.01")  # menor variação de preço permitida
PRECO_INICIAL = Decimal("4.50")  # preço no tick 0; deve ser múltiplo do TICK_SIZE

# ===== População =====
QUANTIDADE_FUNDAMENTALISTAS = 10  # número de agentes fundamentalistas
QUANTIDADE_CHARTISTAS = 10  # número de agentes chartistas
SALDO_MINIMO = 80  # caixa inicial mínimo sorteado por agente
SALDO_MAXIMO = 120  # caixa inicial máximo sorteado por agente
ACOES_MINIMAS = 5  # ações iniciais mínimas sorteadas por agente
ACOES_MAXIMAS = 20  # ações iniciais máximas sorteadas por agente

# ===== Ordens (todos os agentes) =====
AJUSTE_PRECO_LIMITE = Decimal("0.01")  # compra oferta preço atual + ajuste; venda, preço atual - ajuste
QUANTIDADE_MAXIMA_ORDEM = 5  # teto de ações por ordem; limita quanto o preço mexe por tick

# ===== Fundamentalistas =====
VALOR_FUNDAMENTAL_MINIMO = Decimal("3.80")  # menor preço "justo" sorteado
VALOR_FUNDAMENTAL_MAXIMO = Decimal("4.40")  # maior preço "justo" sorteado
CUSTO_INFORMACAO_MINIMO = Decimal("0.05")  # menor custo de informação pago por tick
CUSTO_INFORMACAO_MAXIMO = Decimal("0.15")  # maior custo de informação pago por tick
TOLERANCIA_FUNDAMENTALISTA = Decimal("0.02")  # só negocia se |valor justo - preço| for pelo menos isso
PASSO_QUANTIDADE_FUNDAMENTALISTA = Decimal("2")  # a cada esse valor de diferença, +1 ação na ordem

# ===== Chartistas =====
JANELA_MINIMA = 2  # menor número de ticks passados usados para medir a tendência (mínimo 2)
JANELA_MAXIMA = 5  # maior número de ticks passados usados para medir a tendência
SENSIBILIDADES = (Decimal("0.50"), Decimal("1.00"), Decimal("1.50"))  # opções: quanto a tendência aumenta a quantidade
PROBABILIDADES_INICIAIS = (Decimal("0.50"), Decimal("0.75"), Decimal("1.00"))  # opções: chance de agir no 1º tick, sem histórico
PROBABILIDADES_REVERSAO = (Decimal("0.25"), Decimal("0.50"), Decimal("0.75"))  # opções: chance de agir contra a tendência
QUANTIDADE_SEM_TENDENCIA = 1  # ações negociadas quando não há tendência (lado sorteado)



def criar_agentes(
    quantidade_fundamentalistas: int,
    quantidade_chartistas: int,
) -> list[AgenteFundamentalista | AgenteChartista]:
    if quantidade_fundamentalistas < 1 or quantidade_chartistas < 1:
        raise ValueError("Configure pelo menos um agente de cada estratégia.")

    agentes: list[AgenteFundamentalista | AgenteChartista] = []
    rng = Random(SEMENTE_POPULACAO)

    for indice in range(quantidade_fundamentalistas):
        valor_fundamental = Decimal(
            rng.randint(
                int(VALOR_FUNDAMENTAL_MINIMO * 100),
                int(VALOR_FUNDAMENTAL_MAXIMO * 100),
            )
        ) / Decimal("100")
        custo_informacao = Decimal(
            rng.randint(
                int(CUSTO_INFORMACAO_MINIMO * 100),
                int(CUSTO_INFORMACAO_MAXIMO * 100),
            )
        ) / Decimal("100")
        agentes.append(
            AgenteFundamentalista(
                id=indice,
                nome=f"Agente Fundamentalista {indice + 1}",
                saldo=Decimal(rng.randint(SALDO_MINIMO, SALDO_MAXIMO)),
                valor_fundamental=valor_fundamental,
                quantidade_ativo=rng.randint(ACOES_MINIMAS, ACOES_MAXIMAS),
                custo_informacao=custo_informacao,
                tolerancia=TOLERANCIA_FUNDAMENTALISTA,
                passo_quantidade=PASSO_QUANTIDADE_FUNDAMENTALISTA,
                ajuste_preco_limite=AJUSTE_PRECO_LIMITE,
                quantidade_maxima_ordem=QUANTIDADE_MAXIMA_ORDEM,
            )
        )

    primeiro_id_chartista = quantidade_fundamentalistas
    for indice in range(quantidade_chartistas):
        agentes.append(
            AgenteChartista(
                id=primeiro_id_chartista + indice,
                nome=f"Agente Chartista {indice + 1}",
                saldo=Decimal(rng.randint(SALDO_MINIMO, SALDO_MAXIMO)),
                quantidade_ativo=rng.randint(ACOES_MINIMAS, ACOES_MAXIMAS),
                janela=rng.randint(JANELA_MINIMA, JANELA_MAXIMA),
                sensibilidade=rng.choice(SENSIBILIDADES),
                probabilidade_inicial=rng.choice(PROBABILIDADES_INICIAIS),
                probabilidade_reversao=rng.choice(PROBABILIDADES_REVERSAO),
                quantidade_sem_tendencia=QUANTIDADE_SEM_TENDENCIA,
                ajuste_preco_limite=AJUSTE_PRECO_LIMITE,
                quantidade_maxima_ordem=QUANTIDADE_MAXIMA_ORDEM,
            )
        )

    return agentes


def criar_simulacao() -> SimulacaoMercadoArtificial:
    ativo = Ativo(
        ticker=TICKER,
        tipo=TipoAtivo.ACAO,
        nome=NOME_ATIVO,
        moeda=MOEDA,
        tick_size=TICK_SIZE,
    )
    agentes = criar_agentes(
        quantidade_fundamentalistas=QUANTIDADE_FUNDAMENTALISTAS,
        quantidade_chartistas=QUANTIDADE_CHARTISTAS,
    )
    return SimulacaoMercadoArtificial(
        ativo=ativo,
        preco_inicial=PRECO_INICIAL,
        agentes=list(agentes),
        configuracao=ConfiguracaoSimulacao(
            quantidade_ticks=QUANTIDADE_TICKS,
            semente=SEMENTE_SIMULACAO,
        ),
    )


def mostrar_grafico_precos(simulacao: SimulacaoMercadoArtificial) -> None:
    precos = simulacao.historico_precos
    observacoes = range(len(precos))

    plt.figure(figsize=(11, 5))
    plt.plot(observacoes, precos, linewidth=1.5)
    plt.title(f"Preço da Ação ao longo da simulação")
    plt.xlabel("Observação (0 = preço inicial; 1 = após o tick 0)")
    plt.ylabel("Preço")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


def main() -> None:
    simulacao = criar_simulacao()
    for _ in range(simulacao.configuracao.quantidade_ticks):
        tick = simulacao.simulacao.tempo_atual.tick
        transacoes = simulacao.executar_tick()
        if tick % IMPRIMIR_A_CADA_N_TICKS == 0:
            print(simulacao.resumo_tick(tick, transacoes))
            print()
    if MOSTRAR_GRAFICO:
        mostrar_grafico_precos(simulacao)


if __name__ == "__main__":
    main()