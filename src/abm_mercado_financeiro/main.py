import argparse
from decimal import Decimal
from math import fsum, log1p
from random import Random

import matplotlib.pyplot as plt
from mercadolab.api.ativo import Ativo, TipoAtivo

from .agents import AgenteChartista, AgenteFundamentalista
from .simulation import ConfiguracaoSimulacao, SimulacaoMercadoArtificial

# ===== Configurações Gerais - Constantes Flexíveis =====

# ===== Simulação =====
QUANTIDADE_TICKS = 1000  # quantos ticks (rodadas de negociação) a simulação executa
SEMENTE_POPULACAO = 30  # reproduz o sorteio dos agentes (saldo, ações, parâmetros)
SEMENTE_SIMULACAO = 50  # reproduz os sorteios durante os ticks (decisões e ordem das ordens)

# ===== Saída =====
MOSTRAR_GRAFICO = True  # abre o gráfico de preços ao final

# ===== Ativo =====
TICKER = "ACAO"  # código do ativo no mercado
NOME_ATIVO = "Acao Artificial"  # nome descritivo do ativo
MOEDA = "BRL"  # moeda de negociação
TICK_SIZE = Decimal("0.01")  # menor variação de preço permitida
PRECO_INICIAL = Decimal("4.10")  # preço antes do primeiro tick; múltiplo do TICK_SIZE

# ===== População =====
QUANTIDADE_AGENTES = 100  # número total de agentes
SALDO_MINIMO = 80  # caixa inicial mínimo sorteado por agente
SALDO_MAXIMO = 120  # caixa inicial máximo sorteado por agente
ACOES_MINIMAS = 5  # ações iniciais mínimas sorteadas por agente
ACOES_MAXIMAS = 20  # ações iniciais máximas sorteadas por agente

# ===== Ordens (todos os agentes) =====
AJUSTE_PRECO_LIMITE = Decimal("0.01")  # compra oferta preço atual + ajuste; venda, preço atual - ajuste
QUANTIDADE_MAXIMA_ORDEM = 5  # teto de ações por ordem; limita quanto o preço mexe por tick

# ===== Fundamentalistas =====
FRACAO_AJUSTE_FUNDAMENTALISTA = Decimal("0.10")  # fração da diferença até o valor fundamental incorporada na oferta
VALOR_FUNDAMENTAL_MINIMO = Decimal("3.80")  # menor preço "justo" sorteado
VALOR_FUNDAMENTAL_MAXIMO = Decimal("4.40")  # maior preço "justo" sorteado
CUSTO_INFORMACAO_MINIMO = Decimal("0.05")  # menor custo de informação pago por tick
CUSTO_INFORMACAO_MAXIMO = Decimal("0.15")  # maior custo de informação pago por tick
TOLERANCIA_FUNDAMENTALISTA = Decimal("0.05")  # só negocia se |valor justo - preço| for pelo menos isso
PASSO_QUANTIDADE_FUNDAMENTALISTA = Decimal("2")  # a cada esse valor de diferença, +1 ação na ordem

# ===== Chartistas =====
LIMITE_RELATIVO_AJUSTE_CHARTISTA = Decimal("0.05")  # ajuste de preço limitado a 5% do preço atual
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
                fracao_ajuste_fundamentalista=FRACAO_AJUSTE_FUNDAMENTALISTA,
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
                limite_relativo_ajuste_preco=LIMITE_RELATIVO_AJUSTE_CHARTISTA,
                probabilidade_inicial=rng.choice(PROBABILIDADES_INICIAIS),
                probabilidade_reversao=rng.choice(PROBABILIDADES_REVERSAO),
                quantidade_sem_tendencia=QUANTIDADE_SEM_TENDENCIA,
                ajuste_preco_limite=AJUSTE_PRECO_LIMITE,
                quantidade_maxima_ordem=QUANTIDADE_MAXIMA_ORDEM,
            )
        )

    return agentes


def calcular_quantidades(p: int) -> tuple[int, int]:
    if not 0 <= p <= 100:
        raise ValueError("p deve ser uma porcentagem inteira entre 0 e 100.")
    if QUANTIDADE_AGENTES < 2:
        raise ValueError("QUANTIDADE_AGENTES deve ser pelo menos 2.")

    fundamentalistas = (QUANTIDADE_AGENTES * p + 50) // 100
    chartistas = QUANTIDADE_AGENTES - fundamentalistas
    if fundamentalistas < 1 or chartistas < 1:
        raise ValueError("p deve resultar em pelo menos um agente de cada estratégia.")
    return fundamentalistas, chartistas


def criar_simulacao(p: int) -> SimulacaoMercadoArtificial:
    fundamentalistas, chartistas = calcular_quantidades(p)
    ativo = Ativo(
        ticker=TICKER,
        tipo=TipoAtivo.ACAO,
        nome=NOME_ATIVO,
        moeda=MOEDA,
        tick_size=TICK_SIZE,
    )
    agentes = criar_agentes(
        quantidade_fundamentalistas=fundamentalistas,
        quantidade_chartistas=chartistas,
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


def calcular_variacoes(precos: list[Decimal]) -> list[Decimal]:
    return [atual - anterior for anterior, atual in zip(precos, precos[1:])]


def imprimir_series(precos: list[Decimal]) -> None:
    print(f"{'Tick':>7} | {'Preço':>10} | {'Variação':>10}")
    print(f"{'Inicial':>7} | {precos[0]:>10.2f} | {'-':>10}")
    for tick, (preco, variacao) in enumerate(zip(precos[1:], calcular_variacoes(precos))):
        print(f"{tick:>7} | {preco:>10.2f} | {variacao:>+10.2f}")


def calcular_estatisticas_retornos(
    precos: list[Decimal],
) -> tuple[float, float, float | None, float | None]:
    if len(precos) < 2:
        raise ValueError("São necessários pelo menos dois preços para calcular retornos.")
    if any(not preco.is_finite() or preco <= 0 for preco in precos):
        raise ValueError("Os preços devem ser finitos e positivos para calcular retornos.")

    retornos = [
        log1p(float((atual - anterior) / anterior))
        for anterior, atual in zip(precos, precos[1:])
    ]
    media = fsum(retornos) / len(retornos)
    desvios = [retorno - media for retorno in retornos]
    variancia = fsum(desvio ** 2 for desvio in desvios) / len(desvios)
    if variancia == 0:
        return media, variancia, None, None
    assimetria = fsum(desvio ** 3 for desvio in desvios) / len(desvios) / variancia ** 1.5
    curtose = fsum(desvio ** 4 for desvio in desvios) / len(desvios) / variancia ** 2
    return media, variancia, assimetria, curtose


def imprimir_estatisticas(precos: list[Decimal]) -> None:
    media, variancia, assimetria, curtose = calcular_estatisticas_retornos(precos)
    print("\nEstatísticas dos retornos logarítmicos:")
    print(f"Média: {media:.10f}")
    print(f"Variância: {variancia:.10f}")
    if assimetria is None or curtose is None:
        print("Assimetria: indefinida (variância zero)")
        print("Curtose: indefinida (variância zero)")
    else:
        print(f"Assimetria: {assimetria:.10f}")
        print(f"Curtose: {curtose:.10f}")


def mostrar_grafico_precos(precos: list[Decimal]) -> None:
    figura, eixo = plt.subplots(figsize=(11, 5))
    eixo.plot(range(-1, len(precos) - 1), precos, linewidth=1.5)
    eixo.set_title("Preço da ação ao longo da simulação")
    eixo.set_ylabel("Preço")
    eixo.set_xlabel("Tick (-1 = preço inicial)")
    eixo.grid(True, alpha=0.3)
    figura.tight_layout()
    plt.show()


def main() -> None:
    parser = argparse.ArgumentParser(description="Simula um mercado financeiro artificial.")
    parser.add_argument("--p", type=int, required=True, help="porcentagem inteira de fundamentalistas")
    argumentos = parser.parse_args()
    try:
        fundamentalistas, chartistas = calcular_quantidades(argumentos.p)
    except ValueError as erro:
        parser.error(str(erro))

    simulacao = criar_simulacao(argumentos.p)
    print(
        f"Agentes: {fundamentalistas} fundamentalistas "
        f"({fundamentalistas / QUANTIDADE_AGENTES:.2%}) e {chartistas} chartistas."
    )
    for _ in range(simulacao.configuracao.quantidade_ticks):
        simulacao.executar_tick()
    imprimir_series(simulacao.historico_precos)
    imprimir_estatisticas(simulacao.historico_precos)
    if MOSTRAR_GRAFICO:
        mostrar_grafico_precos(simulacao.historico_precos)


if __name__ == "__main__":
    main()