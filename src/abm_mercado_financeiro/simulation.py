from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from random import Random

from mercadolab.api.ativo import Ativo
from mercadolab.api.mercado import Mercado
from mercadolab.api.ordem import LadoOrdem, TipoOrdem
from mercadolab.api.simulacao import Simulacao
from mercadolab.api.tempo import Tempo
from mercadolab.api.transacao import Transacao

from .agents import AgenteBase, AgenteFundamentalista

MECANISMOS_PRECO = ("ultimo_negocio", "ponto_medio", "lote_aquecimento")


class MercadoSemRestricoes(Mercado):
    def _ordem_eh_liquidavel(self, ordem, quantidade, preco) -> bool:
        return True

    def _liquidar_transacao(self, transacao: Transacao) -> None:
        valor = transacao.preco * Decimal(transacao.quantidade)
        transacao.ordem_compra.investidor.carteira.caixa -= valor
        transacao.ordem_venda.investidor.carteira.caixa += valor


@dataclass(frozen=True)
class ConfiguracaoSimulacao:
    quantidade_ticks: int
    semente: int
    validade_ordem_ticks: int = 50
    restringir_recursos: bool = True
    mecanismo_preco: str = "ultimo_negocio"
    semente_populacao: int = 30
    ticks_aquecimento: int = 20
    desvio_aquecimento: Decimal = Decimal("0.01")
    tamanho_lote: int = 40

    def __post_init__(self) -> None:
        if self.quantidade_ticks <= 0:
            raise ValueError("quantidade_ticks deve ser positivo.")
        if self.validade_ordem_ticks < 1:
            raise ValueError("validade_ordem_ticks deve ser pelo menos 1.")
        if self.mecanismo_preco not in MECANISMOS_PRECO:
            raise ValueError(f"mecanismo_preco deve ser um de {MECANISMOS_PRECO}.")
        if self.ticks_aquecimento < 0:
            raise ValueError("ticks_aquecimento não pode ser negativo.")
        if self.desvio_aquecimento < 0:
            raise ValueError("desvio_aquecimento não pode ser negativo.")
        if self.tamanho_lote < 1:
            raise ValueError("tamanho_lote deve ser pelo menos 1.")


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
        self.mercado = (
            Mercado(nome="Mercado Artificial")
            if configuracao.restringir_recursos
            else MercadoSemRestricoes(nome="Mercado Artificial")
        )
        self.mercado.adicionar_ativo(ativo)
        self.simulacao = Simulacao(mercado=self.mercado, tempo_atual=Tempo(tick=0))
        self._ordem_chegada: dict[int, int] = {}
        self._proxima_chegada = 0
        self._valor_fundamental_aquecimento = self._criar_valores_fundamentais()
        self._agentes_por_investidor = {
            id(agente.investidor): agente for agente in agentes
        }

        for agente in agentes:
            agente.vincular_ativo(ativo)
            agente._restringir_recursos = configuracao.restringir_recursos
            agente._usar_posicao_sem_restricao = not configuracao.restringir_recursos
            agente._quantidade_ativo_sem_restricao = agente._quantidade_ativo_inicial
            self.simulacao.adicionar_investidor(agente.investidor)

    def _criar_valores_fundamentais(self) -> dict[int, Decimal]:
        fundamentais = [
            agente.valor_fundamental
            for agente in self.agentes
            if isinstance(agente, AgenteFundamentalista)
        ]
        if not fundamentais:
            return {}
        rng = Random(f"vf-aquecimento-{self.configuracao.semente_populacao}")
        minimo = int(min(fundamentais) * 100)
        maximo = int(max(fundamentais) * 100)
        return {
            id(agente): (
                agente.valor_fundamental
                if isinstance(agente, AgenteFundamentalista)
                else Decimal(rng.randint(minimo, maximo)) / Decimal("100")
            )
            for agente in self.agentes
        }

    def _expirar_ordens_vencidas(self) -> None:
        tempo = self.simulacao.tempo_atual
        livro = self.mercado.obter_livro(self.ativo.ticker)
        for ordem in livro.listar_ordens_compra() + livro.listar_ordens_venda():
            if tempo.tick - ordem.tempo.tick >= self.configuracao.validade_ordem_ticks:
                ordem.expirar()
                livro.remover_ordem(ordem)

    def _preco_aquecimento(self, agente: AgenteBase, tempo: Tempo):
        tick_size = self.ativo.tick_size
        desvio = float(self.configuracao.desvio_aquecimento)
        perturbacao = Decimal(str(self.rng.gauss(0.0, desvio)))
        preco = self.preco_atual * (Decimal("1") + perturbacao)
        preco = max(tick_size, self._arredondar_tick(preco, tick_size))
        valor_fundamental = self._valor_fundamental_aquecimento.get(id(agente))
        if valor_fundamental is None or preco == valor_fundamental:
            return None
        lado = LadoOrdem.COMPRA if valor_fundamental > preco else LadoOrdem.VENDA
        if self.configuracao.restringir_recursos:
            if lado is LadoOrdem.COMPRA and agente.saldo < self.preco_atual:
                return None
            if lado is LadoOrdem.VENDA and agente.quantidade_ativo < 1:
                return None
        return agente.investidor.emitir_ordem(
            ativo=self.ativo,
            lado=lado,
            tipo=TipoOrdem.LIMITADA,
            quantidade=1,
            tempo=tempo,
            preco_limite=preco,
        )

    @staticmethod
    def _arredondar_tick(preco: Decimal, tick_size: Decimal) -> Decimal:
        ticks = (preco / tick_size).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return ticks * tick_size

    def _marcar_chegada(self, ordem) -> None:
        self._ordem_chegada[id(ordem)] = self._proxima_chegada
        self._proxima_chegada += 1

    def _descruzar_livro(self) -> tuple[Transacao, ...]:
        livro = self.mercado.obter_livro(self.ativo.ticker)
        transacoes = []
        while livro.ordens_compra and livro.ordens_venda:
            compra = livro.ordens_compra[0]
            venda = livro.ordens_venda[0]
            if not compra.esta_ativa():
                livro.remover_ordem(compra)
                continue
            if not venda.esta_ativa():
                livro.remover_ordem(venda)
                continue
            if compra.preco_limite < venda.preco_limite:
                break

            quantidade = min(compra.quantidade_restante, venda.quantidade_restante)
            antiga, nova = (
                (compra, venda)
                if self._ordem_chegada[id(compra)] < self._ordem_chegada[id(venda)]
                else (venda, compra)
            )
            preco = antiga.preco_limite
            if not self.mercado._transacao_eh_liquidavel(
                ordem_compra=compra,
                ordem_venda=venda,
                quantidade=quantidade,
                preco=preco,
            ):
                removidas = False
                for ordem in (compra, venda):
                    if not self.mercado._ordem_eh_liquidavel(
                        ordem=ordem, quantidade=quantidade, preco=preco
                    ):
                        ordem.expirar()
                        livro.remover_ordem(ordem)
                        removidas = True
                if not removidas:
                    break
                continue

            transacao = self.mercado._criar_transacao(
                ordem_entrante=nova,
                ordem_em_livro=antiga,
                quantidade=quantidade,
                preco=preco,
            )
            compra.registrar_execucao(quantidade)
            venda.registrar_execucao(quantidade)
            self.mercado._liquidar_transacao(transacao)
            self.mercado._transacoes.append(transacao)
            transacoes.append(transacao)
            for ordem in (compra, venda):
                if not ordem.esta_ativa():
                    livro.remover_ordem(ordem)
        return tuple(transacoes)

    def _executar_lote(self, ordens) -> tuple[Transacao, ...]:
        livro = self.mercado.obter_livro(self.ativo.ticker)
        ordens_existentes = (
            livro.listar_ordens_compra() + livro.listar_ordens_venda()
        )
        for ordem in ordens_existentes:
            if id(ordem) not in self._ordem_chegada:
                self._marcar_chegada(ordem)
        lote = ordens[: self.configuracao.tamanho_lote]
        restantes = ordens[self.configuracao.tamanho_lote :]
        for ordem in lote:
            livro.adicionar_ordem(ordem)
            self._marcar_chegada(ordem)
        transacoes = list(self._descruzar_livro())
        for ordem in restantes:
            transacoes.extend(self.mercado.submeter_ordem(ordem))
            if ordem.esta_ativa():
                self._marcar_chegada(ordem)
        self.simulacao.avancar_tempo()
        return tuple(transacoes)

    def _registrar_transacoes(self, transacoes: tuple[Transacao, ...]) -> None:
        for transacao in transacoes:
            comprador = self._agentes_por_investidor[id(transacao.ordem_compra.investidor)]
            vendedor = self._agentes_por_investidor[id(transacao.ordem_venda.investidor)]
            if not self.configuracao.restringir_recursos:
                comprador._quantidade_ativo_sem_restricao += transacao.quantidade
                vendedor._quantidade_ativo_sem_restricao -= transacao.quantidade
            comprador.transacoes_iniciadas += 1
            vendedor.transacoes_iniciadas += 1
            self.preco_atual = transacao.preco

    def executar_tick(self) -> tuple[Transacao, ...]:
        tempo = self.simulacao.tempo_atual
        self._expirar_ordens_vencidas()
        if (
            self.configuracao.mecanismo_preco == "lote_aquecimento"
            and tempo.tick < self.configuracao.ticks_aquecimento
        ):
            ordens = [
                ordem
                for agente in self.agentes
                if (ordem := self._preco_aquecimento(agente, tempo)) is not None
            ]
        else:
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
        livro = self.mercado.obter_livro(self.ativo.ticker)
        if self.configuracao.mecanismo_preco == "lote_aquecimento":
            transacoes = self._executar_lote(ordens)
        else:
            melhor_compra = [
                ordem.preco_limite
                for ordem in ordens
                if ordem.lado is LadoOrdem.COMPRA
            ] + [
                ordem.preco_limite
                for ordem in livro.listar_ordens_compra()
                if ordem.esta_ativa()
            ]
            melhor_venda = [
                ordem.preco_limite
                for ordem in ordens
                if ordem.lado is LadoOrdem.VENDA
            ] + [
                ordem.preco_limite
                for ordem in livro.listar_ordens_venda()
                if ordem.esta_ativa()
            ]
            transacoes = self.simulacao.executar_tick(ordens)
        self._registrar_transacoes(transacoes)
        if (
            self.configuracao.mecanismo_preco == "ponto_medio"
            and melhor_compra
            and melhor_venda
            and max(melhor_compra) >= min(melhor_venda)
        ):
            self.preco_atual = self._arredondar_tick(
                (max(melhor_compra) + min(melhor_venda)) / 2,
                self.ativo.tick_size,
            )
        self.historico_precos.append(self.preco_atual)
        return tuple(transacoes)

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