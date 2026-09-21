from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
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
    ) -> None:
        if id < 0:
            raise ValueError("id deve ser não negativo.")
        if not nome.strip():
            raise ValueError("nome não pode ser vazio.")
        if saldo < 0:
            raise ValueError("saldo não pode ser negativo.")
        if quantidade_ativo < 0:
            raise ValueError("quantidade_ativo não pode ser negativa.")

        self.id = id
        self.nome = nome
        self.investidor = Investidor(nome=nome)
        self.investidor.carteira.caixa = saldo
        self._quantidade_ativo_inicial = quantidade_ativo
        self.transacoes_iniciadas = 0

    @property
    def saldo(self) -> Decimal:
        return self.investidor.carteira.caixa

    @property
    def quantidade_ativo(self) -> int:
        if not hasattr(self, "_ativo"):
            return 0
        posicao = self.investidor.carteira.obter_posicao(self._ativo)
        return posicao.quantidade if posicao else 0

    def valor_posicao(self, preco_atual: Decimal) -> Decimal:
        return preco_atual * Decimal(self.quantidade_ativo)

    def patrimonio(self, preco_atual: Decimal) -> Decimal:
        return self.saldo + self.valor_posicao(preco_atual)

    def vincular_ativo(self, ativo: Ativo) -> None:
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
        if lado is LadoOrdem.COMPRA:
            quantidade = min(quantidade, int(self.saldo // preco_atual))
        else:
            quantidade = min(quantidade, self.quantidade_ativo)
        if quantidade <= 0:
            return None

        ajuste = Decimal("0.01")
        preco_limite = preco_atual + ajuste if lado is LadoOrdem.COMPRA else max(ajuste, preco_atual - ajuste)
        return self.investidor.emitir_ordem(
            ativo=ativo,
            lado=lado,
            tipo=TipoOrdem.LIMITADA,
            quantidade=quantidade,
            tempo=tempo,
            preco_limite=preco_limite,
        )

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
        custo_informacao: Decimal = Decimal("0.00"),
    ) -> None:
        super().__init__(id, nome, saldo, quantidade_ativo)
        if valor_fundamental <= 0:
            raise ValueError("valor_fundamental deve ser positivo.")
        if custo_informacao < 0:
            raise ValueError("custo_informacao não pode ser negativo.")
        self.valor_fundamental = valor_fundamental
        self.custo_informacao = custo_informacao

    def pagar_custo_informacao(self) -> None:
        self.investidor.carteira.caixa = max(
            Decimal("0"),
            self.saldo - self.custo_informacao,
        )

    def decidir_lado(self, preco_atual, historico_precos, rng):
        diferenca = self.valor_fundamental - preco_atual
        if abs(diferenca) < Decimal("0.02"):
            return None
        quantidade = max(1, min(5, int(abs(diferenca) // Decimal("2")) + 1))
        return (LadoOrdem.COMPRA if diferenca > 0 else LadoOrdem.VENDA, quantidade)


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
        probabilidade_inicial: Decimal = Decimal("1.00"),
        probabilidade_reversao: Decimal = Decimal("0.50"),
    ) -> None:
        super().__init__(id, nome, saldo, quantidade_ativo)
        if janela < 2:
            raise ValueError("janela deve ser pelo menos 2.")
        if not Decimal("0") <= probabilidade_inicial <= Decimal("1"):
            raise ValueError("probabilidade_inicial deve estar entre zero e um.")
        if not Decimal("0") <= probabilidade_reversao <= Decimal("1"):
            raise ValueError("probabilidade_reversao deve estar entre zero e um.")
        self.janela = janela
        self.sensibilidade = sensibilidade
        self.probabilidade_inicial = probabilidade_inicial
        self.probabilidade_reversao = probabilidade_reversao

    def decidir_lado(self, preco_atual, historico_precos, rng):
        if len(historico_precos) < 2:
            if rng.random() >= float(self.probabilidade_inicial):
                return None
            lado = LadoOrdem.COMPRA if rng.random() < 0.5 else LadoOrdem.VENDA
            return lado, 1
        inicio = historico_precos[-self.janela] if len(historico_precos) >= self.janela else historico_precos[0]
        tendencia = preco_atual - inicio
        if tendencia == 0:
            lado = LadoOrdem.COMPRA if rng.random() < 0.5 else LadoOrdem.VENDA
            return lado, 1
        if rng.random() < float(self.probabilidade_reversao):
            tendencia = -tendencia
        quantidade = max(1, min(5, int(abs(tendencia) * self.sensibilidade) + 1))
        return (LadoOrdem.COMPRA if tendencia > 0 else LadoOrdem.VENDA, quantidade)