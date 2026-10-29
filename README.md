# Comparador de listas de fornecedores

**Português** · [English](README.en.md) · [Español](README.es.md)

[![testes](https://github.com/rodrigoteixeiraferreira/comparador-listas-fornecedores/actions/workflows/ci.yml/badge.svg)](https://github.com/rodrigoteixeiraferreira/comparador-listas-fornecedores/actions/workflows/ci.yml)

![Comparador de listas de fornecedores: zero falso positivo como critério de aceite](docs/img/capa_repositorio.png)

Um sistema que lê listas de preço de fornecedores (planilha, PDF e foto), identifica cada linha no cadastro de um
supermercado e diz, produto por produto, quem vende mais barato. O critério de aceite foi um só:
**zero coincidências confirmadas automaticamente onde marca, tamanho ou unidade não batem.**

Este repositório tem duas partes:

- **o estudo de caso** do sistema que entreguei a um supermercado de bairro na Argentina em outubro de 2026: o
  problema, as decisões e os números. O código e os dados desse projeto são do cliente e não estão aqui;
- **uma demo reescrita do zero**, com dados fictícios, que roda e se prova sozinha: o mesmo desenho, um mundo
  inventado e um gabarito para conferir cada decisão.

Marcas, fornecedores, preços e códigos de barras da demo são inventados. As telas do original que aparecem aqui são
réplicas, com dados fictícios.

## O problema

Um supermercado de bairro recebe dezenas de listas de preço por mês, cada fornecedor no seu formato e com as suas
abreviaturas. O comprador tinha montado um comparador com um assistente de IA. O backup desse sistema mostrou dois
números:

- de 5.129 produtos, só 199 (3,9%) tinham preço de dois ou mais fornecedores;
- dos 475 pares que o sistema confirmou sozinho, **63 (13,3%) tinham o tamanho errado**.

A causa era uma só: o sistema comparava a semelhança das palavras, e o tamanho entrava como texto. Um pacote de 1 kg
casava com o de 2 kg com nota máxima, porque o nome coincidia inteiro.

<img src="docs/img/carrossel_1kg_2kg_2.png" width="420" alt="Duas linhas com o mesmo nome e tamanhos diferentes, confirmadas com nota 1,000">

## A tese

1. **Tamanho, unidade e marca são condição, não pontuação.** Se não batem, o par nem é candidato.
2. **A semelhança de texto nunca confirma.** Só ordena os candidatos para a revisão humana.
3. **A IA interpreta e ordena; o banco calcula.** Nenhum preço, quantidade ou diferença sai de um modelo: todo número
   é uma consulta SQL, rastreável até a lista e a data de onde veio.
4. **Pendência acumulada não é defeito; falso positivo é.**

## Arquitetura

```mermaid
flowchart TD
    L["Lista do fornecedor<br/>planilha, PDF ou foto"] --> F{"Formato conhecido?"}
    F -- sim --> A["Leitor<br/>código"]
    F -- "foto" --> I["Duas leituras de IA independentes<br/>só segue o que as duas dizem igual"]
    A --> P{"Portão<br/>7 conferências"}
    I --> P
    P -- "não passou" --> ANT["Vale a lista anterior"]
    P -- passou --> E["Extrator de atributos<br/>marca, tipo, variedade, conteúdo, unidade"]
    E --> C["Cascata em SQL<br/>código de barras, código do fornecedor,<br/>equivalência confirmada, atributos"]
    C --> N["Par com nível de certeza e motivo"]
    N --> W["Comparação de preços"]
    N -- "só o duvidoso" --> H["Revisão humana"]
    H -- "grava o «é», o «não é» e o «a loja não tem»" --> AP["Aprendizado"]
    AP --> C
    N --> AU["Auditoria por amostra"]
    AU -- "erro acima de 2%" --> D["Aquele tipo de decisão<br/>para de decidir sozinho"]
```

| Camada | Tecnologia |
|---|---|
| Banco, regras e cálculo | Postgres no Supabase: migrações versionadas, funções, views, RLS |
| Leitura de listas e extração | Python (openpyxl, pdfplumber) |
| Leitura de foto | dupla leitura por dois modelos diferentes do Claude, com as respostas gravadas |
| Testes | pytest; no GitHub Actions, contra o Supabase local em Docker |
| Desenvolvimento | Claude Code com o MCP do Supabase |

## A demo

Uma semente gera um mundo inteiro: o mercado (251 produtos de 16 marcas inventadas), o cadastro da loja (158
produtos), as listas de setembro e outubro de dois fornecedores (a Mayorista Norte em planilha, sem IVA; a
Distribuidora Andina em PDF, com IVA e abreviada) e a foto de uma lista impressa de um terceiro (o Mercantil Ombú).
O gerador planta armadilhas em lugares sorteados e escreve o **gabarito** de cada linha: qual é o produto certo, ou
nenhum. O sistema nunca lê o gabarito; só os testes leem.

As armadilhas: 1 kg × 2 kg, marca trocada, variedade trocada, pack × unidade avulsa, a palavra a mais que faz outro
produto («SIN TACC»), a abreviatura que o vocabulário não conhece, o preço da caixa fechada, o código de barras de
outro tamanho, o código do fornecedor reaproveitado para outro produto e o preço digitado com um zero a mais.

| O que a demo prova | Resultado |
|---|---|
| Pares confirmados errados, conferidos contra o gabarito | **0**, em 5 mundos (21 listas) |
| Listas estragadas de propósito que o portão segura na conferência certa | **51 de 51** |
| Listas boas que o portão segura | 0 de 20 |
| Perguntas ao revisor no mês seguinte, depois que ele respondeu as do mês anterior | menos da metade |
| A foto lida por dois modelos (Sonnet e Haiku) | 44 de 44 linhas iguais nas duas leituras, e certas |

A auditoria por amostra da semente 1 (o auditor da demo responde pelo gabarito):

| Tipo de decisão | Amostra | Erros | Erro real, com 95% de confiança | Decisão |
|---|---|---|---|---|
| código de barras | 50 | 0 | até 5,8% | segue ligada |
| código do fornecedor | 50 | 0 | até 5,8% | segue ligada |
| atributos idênticos | 40 | 0 | até 7,2% | segue ligada |
| semelhança alta (em teste) | 18 | 18 | — | **desligada** |
| identidade com preço em dúvida (em teste) | 1 | 0 | até 95% | segue em teste: amostra pequena não decide |

### Como rodar

```bash
python -m venv .venv && . .venv/bin/activate     # no Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m pricelists.world --seed 1              # o mundo da semente 1, em generated/seed-1
pytest                                           # sem banco, os testes de banco são pulados

supabase db start                                # Postgres local com as migrações (precisa de Docker)
export DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
pytest                                           # agora com a prova no banco
python -m pricelists.pipeline --seed 1           # carrega, revisa, audita e mostra a conta de cada lista
```

### O que tem onde

| Onde | O quê |
|---|---|
| `src/pricelists/world/` | o gerador do mundo fictício, das listas, da foto e das corrupções |
| `src/pricelists/extract.py` | o extrator de atributos: o que não reconhece fica como «palavra que sobra», nunca adivinhado |
| `src/pricelists/readers.py`, `ai_reader.py` | os leitores de planilha e PDF; a dupla leitura da foto |
| `src/pricelists/gate.py` | o portão de 7 conferências |
| `supabase/migrations/` | o esquema, a cascata em SQL, as views e o RLS |
| `src/pricelists/audit.py` | a auditoria por amostra |
| `prompts/`, `data/recorded/` | o prompt da leitura de foto e as duas leituras gravadas |
| `tests/` | a prova: gerador, extrator, leitores, portão, cascata e auditoria |

### Os limites

- **O mundo e as regras têm o mesmo autor.** As armadilhas saem de sementes, há escritas que o vocabulário não
  conhece de propósito e a prova roda em vários mundos; ainda assim, um mundo gerado é mais bem-comportado que as
  listas reais. O projeto original foi provado com as listas reais; esta demo prova o mecanismo.
- **Os limites do portão** (variação de preço, preço contra custo, continuidade) estão calibrados para este mundo.
- **A foto foi lida uma vez** por dois subagentes do Claude Code, cada um só com a foto e o prompt, e as leituras
  ficaram gravadas: a demo não chama a API. Nesta foto limpa as duas leituras concordaram em tudo; a fila de
  discordância está provada por um teste que planta divergência.
- **O revisor e o auditor da demo são simulados:** respondem pelo gabarito. No original, uma pessoa respondeu.
- **O painel** (comparação, fila de revisão e estado da base) é o próximo passo.

## As decisões que mais pesaram

- **A palavra que sobra.** Sem código de barras, toda palavra que aparece de um lado só precisa ser ruído declarado
  no vocabulário, ou o par não confirma. No original, a regra derrubou 365 pares que pareciam certos.
- **A decisão negativa é dado.** O «não é este» do revisor vale em todos os passos, inclusive no código de barras, e
  a oferta rejeitada não volta. «A loja não tem» também é uma decisão: a linha não volta à revisão.
- **Todo par tem nível e motivo:** 1 decisão humana, 2 código de barras, 3 regra forte, 4 em revisão. Só os níveis
  1 a 3 contam como confirmados; o par em revisão nunca ganha a comparação calado.
- **Identidade e preço são duas perguntas.** O preço muito longe do custo não desfaz a identificação: o produto
  continua identificado e aquela linha só não compete até alguém conferir o preço.
- **A lista nova espera no portão.** Sete conferências antes de substituir a anterior. Enquanto não passa, vale a
  anterior.
- **A máquina tem taxa de erro medida.** Por amostra sorteada, por tipo de decisão, com limite de 2%.

Os detalhes do original estão em [`docs/`](docs/), em português:
[a cascata](docs/01-cascata.md) ·
[medir a IA](docs/02-medir-a-ia.md) ·
[a prova cega](docs/03-prova-cega.md) ·
[desempenho](docs/04-desempenho.md)

## Resultados do projeto original

Em menos de quatro semanas, do banco ao painel:

| Medida | Valor |
|---|---|
| Pares confirmados com marca, tamanho ou unidade incompatível | **0**, em todas as rodadas de checagem |
| Produtos vendidos com fornecedor identificado | 3.002 de 4.353 (69%) |
| Produtos com preço de dois ou mais fornecedores | 1.596 (no sistema anterior, 199) |
| Listas lidas | 88, de planilha, PDF e foto |
| Erro da IA nos pares confirmados, por amostra | 1 em 145 (0,7%); até 3% com 95% de confiança |
| Fornecedor desconhecido (prova cega) | 0 pares errados; 0 a 4 itens por 100 linhas na mesa do comprador |
| Tempo de abertura das telas | de 10 a 19 s (ou erro) para menos de 2 s |

<p>
<img src="docs/img/medir_a_ia.png" width="270" alt="Auditoria da IA por amostra">
<img src="docs/img/fornecedor_desconhecido.png" width="270" alt="Prova cega do fornecedor desconhecido">
<img src="docs/img/site_rapido.png" width="270" alt="Tempo das telas antes e depois">
</p>

### Telas do original

Réplicas fiéis ao desenho do painel, com dados fictícios. O produto era em espanhol.

![Réplica do estado da base](docs/img/tela_estado_replica.png)

![Réplica da comparação de preços](docs/img/tela_comparacao_replica.png)

## Como trabalhei

- **Um documento de regras vigentes**, lido inteiro antes de qualquer proposta. Decisão tomada com dado real não se
  rediscute sem pedido.
- **Cada sessão abre com um brief e fecha com relatório**, índice de versões e limpeza dos arquivos superados.
- **Uma bateria de testes no fim de cada sessão.** Os testes não escrevem no banco real.
- **Migração provada numa cópia** antes do banco de verdade; migração aplicada não se edita.
- **Custo da IA medido** e com teto mensal.

## Contato

Rodrigo Teixeira Ferreira — automação, dados e agentes de IA. Aberto a contratos e a vaga fixa.
[GitHub](https://github.com/rodrigoteixeiraferreira)
