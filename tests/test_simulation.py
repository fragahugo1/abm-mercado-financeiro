from decimal import Decimal
from random import Random

import pytest

from abm_mercado_financeiro.agents import (
    AgenteChartista,
    AgenteFundamentalista,
    AgenteRuidoso,
)
from abm_mercado_financeiro.main import criar_agentes, criar_simulacao as criar_simulacao_padrao
from abm_mercado_financeiro.simulation import ConfiguracaoSimulacao, SimulacaoMercadoArtificial
from mercadolab.api.ativo import Ativo, TipoAtivo
from mercadolab.api.ordem import LadoOrdem, StatusOrdem, TipoOrdem
from mercadolab.api.tempo import Tempo


def criar_simulacao(
    semente: int = 42,
    configuracao: ConfiguracaoSimulacao | None = None,
) -> SimulacaoMercadoArtificial:
    ativo = Ativo(ticker="TEST", tipo=TipoAtivo.ACAO)
    agentes = [
        AgenteFundamentalista(0, "Fundamentalista", Decimal("100"), Decimal("40"), 5),
        AgenteChartista(1, "Chartista", Decimal("100"), 5),
    ]
    return SimulacaoMercadoArtificial(
        ativo,
        Decimal("42"),
        agentes,
        configuracao or ConfiguracaoSimulacao(10, semente, 50),
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


@pytest.mark.parametrize("validade", [0, -1])
def test_configuracao_rejeita_validade_nao_positiva(validade: int) -> None:
    with pytest.raises(ValueError, match="validade_ordem_ticks"):
        ConfiguracaoSimulacao(10, 42, validade)


@pytest.mark.parametrize(
    ("mecanismo", "validade", "tick_venda", "negocia"),
    [
        (mecanismo, validade, tick_venda, negocia)
        for mecanismo in ("ultimo_negocio", "ponto_medio", "lote_aquecimento")
        for validade, tick_venda, negocia in ((50, 49, True), (50, 50, False), (1, 1, False))
    ],
)
def test_ordem_expira_antes_da_negociacao_no_tick_limite(
    mecanismo: str, validade: int, tick_venda: int, negocia: bool, monkeypatch
) -> None:
    simulacao = criar_simulacao()
    simulacao.configuracao = ConfiguracaoSimulacao(
        100, 42, validade, mecanismo_preco=mecanismo, ticks_aquecimento=0
    )
    comprador, vendedor = simulacao.agentes
    compra = comprador.investidor.emitir_ordem(
        simulacao.ativo, LadoOrdem.COMPRA, TipoOrdem.LIMITADA, 1,
        Tempo(tick=0), Decimal("42"),
    )
    simulacao.mercado.submeter_ordem(compra)
    monkeypatch.setattr(comprador, "gerar_ordem", lambda *args: None)

    def gerar_venda(ativo, tempo, preco_atual, historico_precos, rng):
        if tempo.tick != tick_venda:
            return None
        return vendedor.investidor.emitir_ordem(
            ativo, LadoOrdem.VENDA, TipoOrdem.LIMITADA, 1, tempo, Decimal("42")
        )

    monkeypatch.setattr(vendedor, "gerar_ordem", gerar_venda)
    for _ in range(tick_venda):
        assert simulacao.executar_tick() == ()

    transacoes = simulacao.executar_tick()

    assert bool(transacoes) is negocia
    assert compra.status is (StatusOrdem.EXECUTADA if negocia else StatusOrdem.EXPIRADA)
    assert compra not in simulacao.mercado.obter_livro("TEST").listar_ordens_compra()


def test_expiracao_remove_ordens_parciais_e_de_ambos_os_lados(monkeypatch) -> None:
    simulacao = criar_simulacao()
    comprador, vendedor = simulacao.agentes
    livro = simulacao.mercado.obter_livro("TEST")
    for agente in simulacao.agentes:
        monkeypatch.setattr(agente, "gerar_ordem", lambda *args: None)

    compra = comprador.investidor.emitir_ordem(
        simulacao.ativo, LadoOrdem.COMPRA, TipoOrdem.LIMITADA, 2,
        Tempo(tick=0), Decimal("42"),
    )
    venda_parcial = vendedor.investidor.emitir_ordem(
        simulacao.ativo, LadoOrdem.VENDA, TipoOrdem.LIMITADA, 1,
        Tempo(tick=0), Decimal("42"),
    )
    venda = vendedor.investidor.emitir_ordem(
        simulacao.ativo, LadoOrdem.VENDA, TipoOrdem.LIMITADA, 1,
        Tempo(tick=0), Decimal("43"),
    )
    simulacao.mercado.submeter_ordem(compra)
    simulacao.mercado.submeter_ordem(venda_parcial)
    simulacao.mercado.submeter_ordem(venda)
    assert compra.status is StatusOrdem.PARCIALMENTE_EXECUTADA
    assert compra.quantidade_restante == 1

    for _ in range(50):
        simulacao.executar_tick()
    assert compra.esta_ativa() and venda.esta_ativa()

    simulacao.executar_tick()
    assert compra.status is StatusOrdem.EXPIRADA
    assert compra.quantidade_executada == 1
    assert venda.status is StatusOrdem.EXPIRADA
    assert livro.listar_ordens_compra() == []
    assert livro.listar_ordens_venda() == []


def test_fundamentalista_nao_perde_caixa_sem_negociar(monkeypatch) -> None:
    simulacao = criar_simulacao_padrao(20)
    saldos_iniciais = [agente.saldo for agente in simulacao.agentes]
    for agente in simulacao.agentes:
        monkeypatch.setattr(agente, "gerar_ordem", lambda *args: None)

    for _ in range(100):
        assert simulacao.executar_tick() == ()

    assert [agente.saldo for agente in simulacao.agentes] == saldos_iniciais


def test_simulacao_padrao_conserva_caixa_e_acoes() -> None:
    simulacao = criar_simulacao_padrao(20)
    caixa_inicial = sum(agente.saldo for agente in simulacao.agentes)
    acoes_iniciais = sum(agente.quantidade_ativo for agente in simulacao.agentes)

    simulacao.executar()

    assert sum(agente.saldo for agente in simulacao.agentes) == caixa_inicial
    assert sum(agente.quantidade_ativo for agente in simulacao.agentes) == acoes_iniciais


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
        ConfiguracaoSimulacao(5, 42, 50),
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


def test_ordem_respeita_quantidade_maxima_configurada() -> None:
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
    assert ordem.preco_limite == Decimal("7.60")


def test_agente_ruidoso_emite_ordem_limitada_com_preco_na_amplitude() -> None:
    ativo = Ativo(ticker="RUIDO", tipo=TipoAtivo.ACAO)
    agente = AgenteRuidoso(
        0,
        "Ruidoso",
        Decimal("1000"),
        amplitude_preco=Decimal("0.05"),
        quantidade_ordem=2,
        quantidade_ativo=5,
    )
    agente.vincular_ativo(ativo)

    ordem = agente.gerar_ordem(
        ativo, Tempo(tick=0), Decimal("42"), [Decimal("42")], Random(7)
    )

    assert ordem is not None
    assert ordem.quantidade == 2
    assert Decimal("39.90") <= ordem.preco_limite <= Decimal("44.10")
    assert ordem.tipo is TipoOrdem.LIMITADA


@pytest.mark.parametrize(
    ("mecanismo", "ticks_aquecimento"),
    [("ultimo_negocio", 0), ("ponto_medio", 0), ("lote_aquecimento", 0)],
)
def test_mecanismos_de_preco_executam_ordens_cruzadas(
    mecanismo: str, ticks_aquecimento: int, monkeypatch
) -> None:
    simulacao = criar_simulacao()
    simulacao.configuracao = ConfiguracaoSimulacao(
        1,
        42,
        mecanismo_preco=mecanismo,
        ticks_aquecimento=ticks_aquecimento,
        tamanho_lote=2,
    )
    comprador, vendedor = simulacao.agentes

    def gerar_ordem(lado, preco, agente):
        return lambda ativo, tempo, *args: agente.investidor.emitir_ordem(
            ativo,
            lado,
            TipoOrdem.LIMITADA,
            1,
            tempo,
            preco,
        )

    monkeypatch.setattr(
        comprador,
        "gerar_ordem",
        gerar_ordem(LadoOrdem.COMPRA, Decimal("43"), comprador),
    )
    monkeypatch.setattr(
        vendedor,
        "gerar_ordem",
        gerar_ordem(LadoOrdem.VENDA, Decimal("40"), vendedor),
    )

    transacoes = simulacao.executar_tick()

    assert len(transacoes) == 1
    assert simulacao.simulacao.tempo_atual.tick == 1
    if mecanismo == "ponto_medio":
        assert simulacao.preco_atual == Decimal("41.50")
    else:
        assert simulacao.preco_atual in (Decimal("40"), Decimal("43"))


def test_lote_aquecimento_usa_ordens_de_aquecimento_antes_dos_agentes(monkeypatch) -> None:
    simulacao = criar_simulacao_padrao(36, 33)
    simulacao.configuracao = ConfiguracaoSimulacao(
        1, 42, mecanismo_preco="lote_aquecimento", ticks_aquecimento=1
    )

    def falhar_se_chamado(*args):
        raise AssertionError("gerar_ordem não deve ser chamado durante o aquecimento.")

    for agente in simulacao.agentes:
        monkeypatch.setattr(agente, "gerar_ordem", falhar_se_chamado)

    simulacao.executar_tick()

    assert simulacao.simulacao.tempo_atual.tick == 1
    assert len(simulacao.historico_precos) == 2


@pytest.mark.parametrize(
    ("restringir_recursos", "negocia", "posicao_comprador", "posicao_vendedor"),
    [(True, False, 0, 0), (False, True, 1, -1)],
)
def test_modo_sem_restricoes_permite_caixa_negativo_e_venda_a_descoberto(
    restringir_recursos: bool,
    negocia: bool,
    posicao_comprador: int,
    posicao_vendedor: int,
    monkeypatch,
) -> None:
    comprador = AgenteFundamentalista(
        0, "Comprador", Decimal("0"), Decimal("100")
    )
    vendedor = AgenteChartista(1, "Vendedor", Decimal("0"))
    ativo = Ativo(ticker="TEST", tipo=TipoAtivo.ACAO)
    simulacao = SimulacaoMercadoArtificial(
        ativo,
        Decimal("42"),
        [comprador, vendedor],
        ConfiguracaoSimulacao(
            1, 42, restringir_recursos=restringir_recursos
        ),
    )

    def gerar_ordem(lado, agente):
        return lambda ativo, tempo, *args: agente.investidor.emitir_ordem(
            ativo,
            lado,
            TipoOrdem.LIMITADA,
            1,
            tempo,
            Decimal("42"),
        )

    monkeypatch.setattr(comprador, "gerar_ordem", gerar_ordem(LadoOrdem.COMPRA, comprador))
    monkeypatch.setattr(vendedor, "gerar_ordem", gerar_ordem(LadoOrdem.VENDA, vendedor))

    transacoes = simulacao.executar_tick()

    assert bool(transacoes) is negocia
    assert comprador.quantidade_ativo == posicao_comprador
    assert vendedor.quantidade_ativo == posicao_vendedor
    if negocia:
        assert comprador.saldo == Decimal("-42")
        assert vendedor.saldo == Decimal("42")


def test_preco_ordem_fundamentalista_depende_da_distancia_ao_valor_justo() -> None:
    agente = AgenteFundamentalista(
        0,
        "Fundamentalista",
        Decimal("100"),
        Decimal("4.40"),
        quantidade_ativo=5,
        tolerancia=Decimal("0.05"),
    )
    ativo = Ativo(ticker="FUND", tipo=TipoAtivo.ACAO)

    ordem = agente.gerar_ordem(
        ativo, Tempo(tick=0), Decimal("4.10"), [Decimal("4.10")], Random(1)
    )

    assert ordem is not None
    assert ordem.preco_limite == Decimal("4.13")


def test_preco_ordem_chartista_depende_da_tendencia_e_sensibilidade() -> None:
    ativo = Ativo(ticker="CHART", tipo=TipoAtivo.ACAO)
    historico = [Decimal("4.00"), Decimal("4.10")]
    ordens = []
    for indice, sensibilidade in enumerate((Decimal("0.50"), Decimal("1.50"))):
        agente = AgenteChartista(
            indice,
            f"Chartista {indice}",
            Decimal("100"),
            quantidade_ativo=5,
            janela=2,
            sensibilidade=sensibilidade,
            probabilidade_reversao=Decimal("0"),
        )
        ordem = agente.gerar_ordem(
            ativo, Tempo(tick=1), Decimal("4.10"), historico, Random(1)
        )
        assert ordem is not None
        ordens.append(ordem)

    assert [ordem.preco_limite for ordem in ordens] == [
        Decimal("4.15"),
        Decimal("4.25"),
    ]