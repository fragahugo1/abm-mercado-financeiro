# Mercado financeiro artificial

Simulação de um mercado artificial com agentes fundamentalistas e chartistas.
O projeto usa Python e a biblioteca MercadoLab como motor de negociação.

## Requisitos

- Python 3.11 ou superior;

## Instalação

Abra o terminal e execute:

```powershell
git clone https://github.com/fragahugo1/abm-mercado-financeiro.git
cd abm-mercado-financeiro
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

## Executar a simulação

Informe `--p` como uma porcentagem inteira de agentes fundamentalistas. Por
exemplo:

```powershell
abm-mercado-financeiro --p 20
```

Com as configurações padrão, a simulação executa 1.000 ticks e cria 100 agentes:
20 fundamentalistas e 80 chartistas. São necessários pelo menos um agente de
cada estratégia; por isso, com 100 agentes, `p` deve estar entre 1 e 99.


## Saídas e cálculos

- **Preço inicial:** R$ 4,10, mostrado antes do tick 0.
- **Variação:** preço atual menos o preço anterior, em reais. Para 1.000 ticks,
  são mostrados 1.001 preços e 1.000 variações.
- **Retorno logarítmico:** `ln(preço atual / preço anterior)`.
- **Estatísticas:** média, variância populacional (dividida por N), assimetria e curtose convencional. Não são aplicadas correções amostrais. Se a variância for zero, assimetria e curtose são indefinidas.

Cada tick representa uma rodada da simulação.

## Parâmetros técnicos

As configurações avançadas e as sementes estão em
[main.py](src/abm_mercado_financeiro/main.py). Por padrão, os valores sorteados
para os fundamentalistas variam entre R$ 3,80 e R$ 4,40. Na formação dos preços
das ordens:

- fundamentalistas incorporam 10% da diferença entre o preço atual e seu valor
  fundamental;
- chartistas ajustam suas ofertas conforme a tendência e sua sensibilidade,
  limitando o ajuste a 5% do preço atual;
- os preços das ordens respeitam o tick size configurado.

Esses valores são parâmetros do modelo e podem ser alterados para experimentos.
Os resultados podem mudar ao alterar parâmetros, sementes ou a porcentagem `p`.

## Testes 

Para instalar as dependências de desenvolvimento e executar os testes:

```powershell
python -m pip install -e ".[dev]"
python -m pytest
```
