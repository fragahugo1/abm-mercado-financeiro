# Mercado financeiro artificial

Simulação de um mercado artificial com agentes fundamentalistas, chartistas e
e de ruídos. O projeto usa Python e a biblioteca MercadoLab como motor de
negociação.

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

Informe `--p` como a porcentagem inteira de fundamentalistas e `--p-ruido`
como a porcentagem inteira de agentes ruidosos. Os chartistas recebem a
porcentagem restante. Por exemplo, para testar a composição 36%/33%/31%:

```powershell
abm-mercado-financeiro --p 36 --p-ruido 33
```

Com as constantes padrão, a simulação executa 1000 ticks e cria 150 agentes.
Os percentuais são convertidos em quantidades inteiras por arredondamento; é
necessário haver pelo menos um fundamentalista e um chartista. Os chartistas
representam o restante depois de contabilizados os outros dois grupos.


## Saídas e cálculos

- **Preço inicial:** R$ 100,00, mostrado antes do tick 0.
- **Variação:** preço atual menos o preço anterior, em reais. Para 1.000 ticks,
  são mostrados 1.001 preços e 1.000 variações.
- **Retorno logarítmico:** `ln(preço atual / preço anterior)`.
- **Estatísticas:** média, variância populacional (dividida por N), assimetria e curtose convencional. Não são aplicadas correções amostrais. Se a variância for zero, assimetria e curtose são indefinidas.

Cada tick representa uma rodada da simulação.

## Parâmetros técnicos

As configurações avançadas e as sementes estão em
[main.py](src/abm_mercado_financeiro/main.py). Os valores fundamentais são
sorteados entre R$ 90 e R$ 110. A composição padrão do experimento pode ser
informada com `--p 36 --p-ruido 33`. Na formação dos preços das ordens:

- fundamentalistas incorporam 10% da diferença entre o preço atual e seu valor
  fundamental;
- chartistas ajustam suas ofertas conforme a tendência e sua sensibilidade,
  limitando o ajuste a 5% do preço atual;
- ruidosos escolhem aleatoriamente o lado e um preço-limite numa faixa de 5%
  em torno do preço atual;
- os preços das ordens respeitam o tick size configurado.

O mecanismo de preço é selecionado pela constante `MECANISMO_PRECO`: `ultimo_negocio`,
`ponto_medio` ou `lote_aquecimento`. As ordens expiram após o prazo configurado
em `VALIDADE_ORDEM_TICKS`. Por padrão, caixa e posições não podem ficar
negativos; `RESTRINGIR_RECURSOS = False` habilita a variante experimental com
caixa negativo e venda a descoberto.

As sementes fixas tornam a execução reproduzível com a mesma configuração.
Parâmetros, sementes e percentuais podem ser alterados para experimentos; a
rotina de calibração histórica do notebook não está incluída na aplicação.

## Testes 

Para instalar as dependências de desenvolvimento e executar os testes:

```powershell
python -m pip install -e ".[dev]"
python -m pytest
```
