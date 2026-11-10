from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from random import Random

from mercadolab.api.ativo import Ativo
from mercadolab.api.mercado import Mercado
from mercadolab.api.simulacao import Simulacao
from mercadolab.api.tempo import Tempo
from mercadolab.api.transacao import Transacao

from .agents import AgenteBase


@dataclass(frozen=True)
class ConfiguracaoSimulacao:
    quantidade_ticks: int
    semente: int
    validade_ordem_ticks: int = 50

    def __post_init__(self) -> None:
        if self.quantidade_ticks <= 0:
            raise ValueError("quantidade_ticks deve ser positivo.")
        if self.validade_ordem_ticks < 1:
            raise ValueError("validade_ordem_ticks deve ser pelo menos 1.")


class SimulacaoMercadoArtificial:
    """Orquestra agentes externos e usa o MercadoLab como motor de negociação."""

    def __init__(
        self,
        ativo: Ativo,
        preco_inicial: Decimal,
        agentes: list[AgenteBase],
        configuracao: ConfiguracaoSimulacao,
    ) -> None:
        if preco_inicial <= 0 or not ativo.validar_preco(preco_inicial):
            raise ValueError("preco_inicial deve respeitar o tick size do ativo.")
        if len(agentes) < 2:
            raise ValueError("a simulação exige pelo menos dois agentes.")

        self.ativo = ativo
        self.preco_atual = preco_inicial
        self.historico_precos = [preco_inicial]
        self.agentes = agentes
        self.configuracao = configuracao
        self.rng = Random(configuracao.semente)
        self.mercado = Mercado(nome="Mercado Artificial")
        self.mercado.adicionar_ativo(ativo)
        self.simulacao = Simulacao(mercado=self.mercado, tempo_atual=Tempo(tick=0))

        for agente in agentes:
            agente.vincular_ativo(ativo)
            self.simulacao.adicionar_investidor(agente.investidor)

    def executar_tick(self) -> tuple[Transacao, ...]:
        tempo = self.simulacao.tempo_atual
        livro = self.mercado.obter_livro(self.ativo.ticker)
        for ordem in livro.listar_ordens_compra() + livro.listar_ordens_venda():
            if tempo.tick - ordem.tempo.tick >= self.configuracao.validade_ordem_ticks:
                ordem.expirar()
                livro.remover_ordem(ordem)
        ordens = [
            ordem
            for agente in self.agentes
            if (ordem := agente.gerar_ordem(
                self.ativo,
                tempo,
                self.preco_atual,
                self.historico_precos,
                self.rng,
            )) is not None
        ]
        self.rng.shuffle(ordens)
        transacoes = self.simulacao.executar_tick(ordens)
        for transacao in transacoes:
            self.preco_atual = transacao.preco
            for agente in self.agentes:
                envolvidos = (
                    transacao.ordem_compra.investidor,
                    transacao.ordem_venda.investidor,
                )
                if agente.investidor in envolvidos:
                    agente.transacoes_iniciadas += 1
        self.historico_precos.append(self.preco_atual)
        return transacoes

    def executar(self) -> list[tuple[int, tuple[Transacao, ...]]]:
        resultados = []
        for _ in range(self.configuracao.quantidade_ticks):
            tick = self.simulacao.tempo_atual.tick
            resultados.append((tick, self.executar_tick()))
        return resultados

    def resumo_tick(self, tick: int, transacoes: tuple[Transacao, ...] = ()) -> str:
        largura_nome = max(len(agente.nome) for agente in self.agentes)
        colunas = (
            f"{'Agente':<{largura_nome}} | {'Caixa':>10} | {'Ações':>6} | "
            f"{'Valor em Ações':>14} | {'Patrimônio':>10}"
        )
        largura = len(colunas)
        linhas = [
            "=" * largura,
            f"TICK {tick}  |  Preço da Ação: {self.preco_atual:.2f}  |  "
            f"Transações: {len(transacoes)}",
            "=" * largura,
        ]

        grupos: dict[str, list[AgenteBase]] = {}
        for agente in self.agentes:
            grupos.setdefault(agente.tipo, []).append(agente)

        for agentes_grupo in grupos.values():
            titulo = f"{agentes_grupo[0].tipo.upper()}S ({len(agentes_grupo)})"
            linhas.extend(["", titulo, colunas, "-" * largura])
            for agente in agentes_grupo:
                linhas.append(
                    f"{agente.nome:<{largura_nome}} | {agente.saldo:>10.2f} | "
                    f"{agente.quantidade_ativo:>6} | "
                    f"{agente.valor_posicao(self.preco_atual):>14.2f} | "
                    f"{agente.patrimonio(self.preco_atual):>10.2f}"
                )
        return "\n".join(linhas)