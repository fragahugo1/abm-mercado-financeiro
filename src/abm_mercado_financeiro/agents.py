from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal, ROUND_HALF_UP
from random import Random
from typing import TYPE_CHECKING

from mercadolab.api.ativo import Ativo
from mercadolab.api.investidor import Investidor
from mercadolab.api.ordem import LadoOrdem, Ordem, TipoOrdem
from mercadolab.api.tempo import Tempo

if TYPE_CHECKING:
    from collections.abc import Sequence


class AgenteBase(ABC):
    """Identidade e estado de um investidor do mercado artificial."""

    tipo = "base"

    def __init__(
        self,
        id: int,
        nome: str,
        saldo: Decimal,
        quantidade_ativo: int = 0,
        ajuste_preco_limite: Decimal = Decimal("0.01"),
        quantidade_maxima_ordem: int = 5,
    ) -> None:
        if id < 0:
            raise ValueError("id deve ser não negativo.")
        if not nome.strip():
            raise ValueError("nome não pode ser vazio.")
        if saldo < 0:
            raise ValueError("saldo não pode ser negativo.")
        if quantidade_ativo < 0:
            raise ValueError("quantidade_ativo não pode ser negativa.")
        if ajuste_preco_limite <= 0:
            raise ValueError("ajuste_preco_limite deve ser positivo.")
        if quantidade_maxima_ordem < 1:
            raise ValueError("quantidade_maxima_ordem deve ser pelo menos 1.")

        self.ajuste_preco_limite = ajuste_preco_limite
        self.quantidade_maxima_ordem = quantidade_maxima_ordem
        self.id = id
        self.nome = nome
        self.investidor = Investidor(nome=nome)
        self.investidor.carteira.caixa = saldo
        self._quantidade_ativo_inicial = quantidade_ativo
        self.transacoes_iniciadas = 0
        self._quantidade_ativo_sem_restricao = quantidade_ativo
        self._usar_posicao_sem_restricao = False
        self._restringir_recursos = True

    @property
    def saldo(self) -> Decimal:
        return self.investidor.carteira.caixa

    @property
    def quantidade_ativo(self) -> int:
        if self._usar_posicao_sem_restricao:
            return self._quantidade_ativo_sem_restricao
        if not hasattr(self, "_ativo"):
            return 0
        posicao = self.investidor.carteira.obter_posicao(self._ativo)
        return posicao.quantidade if posicao else 0

    def valor_posicao(self, preco_atual: Decimal) -> Decimal:
        return preco_atual * Decimal(self.quantidade_ativo)

    def patrimonio(self, preco_atual: Decimal) -> Decimal:
        return self.saldo + self.valor_posicao(preco_atual)

    def vincular_ativo(self, ativo: Ativo) -> None:
        if not ativo.validar_preco(self.ajuste_preco_limite):
            raise ValueError("ajuste_preco_limite deve ser múltiplo do tick size do ativo.")
        self._ativo = ativo
        if self._quantidade_ativo_inicial:
            from mercadolab.api.posicao import Posicao

            self.investidor.carteira.posicoes[ativo.ticker] = Posicao(
                ativo=ativo,
                quantidade=self._quantidade_ativo_inicial,
                preco_medio=Decimal("0.01"),
            )

    def gerar_ordem(
        self,
        ativo: Ativo,
        tempo: Tempo,
        preco_atual: Decimal,
        historico_precos: Sequence[Decimal],
        rng: Random,
    ) -> Ordem | None:
        decisao = self.decidir_lado(preco_atual, historico_precos, rng)
        if decisao is None:
            return None

        lado, quantidade = decisao
        quantidade = min(quantidade, self.quantidade_maxima_ordem)
        if self._restringir_recursos:
            if lado is LadoOrdem.COMPRA:
                quantidade = min(quantidade, int(self.saldo // preco_atual))
            else:
                quantidade = min(quantidade, self.quantidade_ativo)
        if quantidade <= 0:
            return None

        preco_limite = self.calcular_preco_limite(
            lado, ativo, preco_atual, historico_precos
        )
        return self.investidor.emitir_ordem(
            ativo=ativo,
            lado=lado,
            tipo=TipoOrdem.LIMITADA,
            quantidade=quantidade,
            tempo=tempo,
            preco_limite=preco_limite,
        )

    def calcular_preco_limite(
        self,
        lado: LadoOrdem,
        ativo: Ativo,
        preco_atual: Decimal,
        historico_precos: Sequence[Decimal],
    ) -> Decimal:
        ajuste = self.ajuste_preco_limite
        preco = (
            preco_atual + ajuste
            if lado is LadoOrdem.COMPRA
            else max(ajuste, preco_atual - ajuste)
        )
        return self._arredondar_preco(preco, ativo)

    @staticmethod
    def _arredondar_preco(preco: Decimal, ativo: Ativo) -> Decimal:
        quantidade_ticks = (preco / ativo.tick_size).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
        return max(ativo.tick_size, quantidade_ticks * ativo.tick_size)

    @abstractmethod
    def decidir_lado(
        self,
        preco_atual: Decimal,
        historico_precos: Sequence[Decimal],
        rng: Random,
    ) -> tuple[LadoOrdem, int] | None:
        """Retorna lado e quantidade, ou None quando o agente não negocia."""


class AgenteFundamentalista(AgenteBase):
    tipo = "fundamentalista"

    def __init__(
        self,
        id: int,
        nome: str,
        saldo: Decimal,
        valor_fundamental: Decimal,
        quantidade_ativo: int = 0,
        tolerancia: Decimal = Decimal("0.02"),
        passo_quantidade: Decimal = Decimal("2"),
        fracao_ajuste_fundamentalista: Decimal = Decimal("0.10"),
        ajuste_preco_limite: Decimal = Decimal("0.01"),
        quantidade_maxima_ordem: int = 5,
    ) -> None:
        super().__init__(
            id, nome, saldo, quantidade_ativo, ajuste_preco_limite, quantidade_maxima_ordem
        )
        if tolerancia < 0:
            raise ValueError("tolerancia não pode ser negativa.")
        if passo_quantidade <= 0:
            raise ValueError("passo_quantidade deve ser positivo.")
        if valor_fundamental <= 0:
            raise ValueError("valor_fundamental deve ser positivo.")
        if not Decimal("0") < fracao_ajuste_fundamentalista <= Decimal("1"):
            raise ValueError("fracao_ajuste_fundamentalista deve estar entre zero e um.")
        self.valor_fundamental = valor_fundamental
        self.tolerancia = tolerancia
        self.passo_quantidade = passo_quantidade
        self.fracao_ajuste_fundamentalista = fracao_ajuste_fundamentalista

    def decidir_lado(self, preco_atual, historico_precos, rng):
        diferenca = self.valor_fundamental - preco_atual
        if abs(diferenca) < self.tolerancia:
            return None
        quantidade = int(abs(diferenca) // self.passo_quantidade) + 1
        return (LadoOrdem.COMPRA if diferenca > 0 else LadoOrdem.VENDA, quantidade)

    def calcular_preco_limite(self, lado, ativo, preco_atual, historico_precos):
        diferenca = self.valor_fundamental - preco_atual
        preco = preco_atual + self.fracao_ajuste_fundamentalista * diferenca
        return self._arredondar_preco(preco, ativo)


class AgenteChartista(AgenteBase):
    tipo = "chartista"

    def __init__(
        self,
        id: int,
        nome: str,
        saldo: Decimal,
        quantidade_ativo: int = 0,
        janela: int = 3,
        sensibilidade: Decimal = Decimal("1.00"),
        limite_relativo_ajuste_preco: Decimal = Decimal("0.05"),
        probabilidade_inicial: Decimal = Decimal("1.00"),
        probabilidade_reversao: Decimal = Decimal("0.50"),
        quantidade_sem_tendencia: int = 1,
        ajuste_preco_limite: Decimal = Decimal("0.01"),
        quantidade_maxima_ordem: int = 5,
    ) -> None:
        super().__init__(
            id, nome, saldo, quantidade_ativo, ajuste_preco_limite, quantidade_maxima_ordem
        )
        if quantidade_sem_tendencia < 1:
            raise ValueError("quantidade_sem_tendencia deve ser pelo menos 1.")
        if janela < 2:
            raise ValueError("janela deve ser pelo menos 2.")
        if not Decimal("0") < limite_relativo_ajuste_preco <= Decimal("1"):
            raise ValueError("limite_relativo_ajuste_preco deve estar entre zero e um.")
        if not Decimal("0") <= probabilidade_inicial <= Decimal("1"):
            raise ValueError("probabilidade_inicial deve estar entre zero e um.")
        if not Decimal("0") <= probabilidade_reversao <= Decimal("1"):
            raise ValueError("probabilidade_reversao deve estar entre zero e um.")
        self.janela = janela
        self.sensibilidade = sensibilidade
        self.limite_relativo_ajuste_preco = limite_relativo_ajuste_preco
        self.probabilidade_inicial = probabilidade_inicial
        self.probabilidade_reversao = probabilidade_reversao
        self.quantidade_sem_tendencia = quantidade_sem_tendencia

    def decidir_lado(self, preco_atual, historico_precos, rng):
        if len(historico_precos) < 2:
            if rng.random() >= float(self.probabilidade_inicial):
                return None
            lado = LadoOrdem.COMPRA if rng.random() < 0.5 else LadoOrdem.VENDA
            return lado, self.quantidade_sem_tendencia
        tendencia = self._calcular_tendencia(preco_atual, historico_precos)
        if tendencia == 0:
            lado = LadoOrdem.COMPRA if rng.random() < 0.5 else LadoOrdem.VENDA
            return lado, self.quantidade_sem_tendencia
        if rng.random() < float(self.probabilidade_reversao):
            tendencia = -tendencia
        quantidade = int(abs(tendencia) * self.sensibilidade) + 1
        return (LadoOrdem.COMPRA if tendencia > 0 else LadoOrdem.VENDA, quantidade)

    def calcular_preco_limite(self, lado, ativo, preco_atual, historico_precos):
        tendencia = self._calcular_tendencia(preco_atual, historico_precos)
        ajuste_maximo = preco_atual * self.limite_relativo_ajuste_preco
        ajuste = max(
            self.ajuste_preco_limite,
            min(abs(tendencia) * self.sensibilidade, ajuste_maximo),
        )
        preco = (
            preco_atual + ajuste
            if lado is LadoOrdem.COMPRA
            else max(ativo.tick_size, preco_atual - ajuste)
        )
        return self._arredondar_preco(preco, ativo)

    def _calcular_tendencia(
        self,
        preco_atual: Decimal,
        historico_precos: Sequence[Decimal],
    ) -> Decimal:
        if len(historico_precos) < 2:
            return Decimal("0")
        inicio = (
            historico_precos[-self.janela]
            if len(historico_precos) >= self.janela
            else historico_precos[0]
        )
        return preco_atual - inicio


class AgenteRuidoso(AgenteBase):
    """Agente que escolhe o lado aleatoriamente e posiciona ordem em torno do preço atual."""

    tipo = "ruidoso"

    def __init__(
        self,
        id: int,
        nome: str,
        saldo: Decimal,
        amplitude_preco: Decimal,
        quantidade_ordem: int = 2,
        quantidade_ativo: int = 0,
        ajuste_preco_limite: Decimal = Decimal("0.01"),
        quantidade_maxima_ordem: int = 5,
    ) -> None:
        super().__init__(
            id, nome, saldo, quantidade_ativo, ajuste_preco_limite, quantidade_maxima_ordem
        )
        if not Decimal("0") <= amplitude_preco < Decimal("1"):
            raise ValueError("amplitude_preco deve estar entre zero e um.")
        if quantidade_ordem < 1:
            raise ValueError("quantidade_ordem deve ser pelo menos 1.")
        self.amplitude_preco = amplitude_preco
        self.quantidade_ordem = quantidade_ordem
        self._variacao_preco = Decimal("0")

    def decidir_lado(self, preco_atual, historico_precos, rng):
        lado = LadoOrdem.COMPRA if rng.random() < 0.5 else LadoOrdem.VENDA
        variacao = rng.uniform(-float(self.amplitude_preco), float(self.amplitude_preco))
        self._variacao_preco = Decimal(str(variacao))
        return lado, self.quantidade_ordem

    def calcular_preco_limite(self, lado, ativo, preco_atual, historico_precos):
        preco = preco_atual * (Decimal("1") + self._variacao_preco)
        return self._arredondar_preco(max(ativo.tick_size, preco), ativo)