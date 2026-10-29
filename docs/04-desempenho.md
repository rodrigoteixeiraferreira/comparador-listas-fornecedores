# 4. O painel rápido, sem mudar o que ele mostra

Dias antes do teste final, o painel não aguentava: duas telas de revisão não abriam e quase toda aba levava uns
11 segundos ou caía. Uma sessão inteira foi para isso, com uma regra: **as telas não podiam mudar nada do que
mostram. Só a velocidade.**

<img src="img/site_rapido.png" width="420" alt="13 de 16 medições caíam; depois, todas abrem em menos de 2 segundos">

## 1. A medida primeiro

- cada aba, nos dois perfis de usuário, medida como o site a serve: contra o banco real, com uma sessão de verdade
  e o registro de cada consulta que a página faz;
- os logs do banco: numa noite de uso, 95 consultas cortadas pelo limite de 8 segundos da API;
- o plano de cada consulta.

## 2. A causa

Não era um defeito: era o trabalho por página. As telas de revisão recalculavam tudo a cada contagem, cada página
disparava de 10 a 22 consultas ao mesmo tempo, o banco é pequeno, a API abre conexões novas a cada rajada e a
primeira consulta de cada conexão nova planeja do zero.

## 3. A armadilha

Uma versão «mais rápida», com muitas partes, ficou muito pior em conexão fria: 24 segundos contra 1. Só a leitura
de uma tabela simples aguenta a rajada. Isso só apareceu porque a medida era a rajada fria, e não a consulta isolada.

## 4. A correção

O preço da lista e o custo do cadastro só mudam quando uma rodada de processamento roda. Então:

- **o pesado é calculado no fim da rodada** e a tela lê o resultado pronto;
- **o que um clique grava vale na hora**, por um filtro pequeno ou por um gatilho que recalcula só o cartão ou o
  produto que o clique tocou.

## 5. A prova

- as 49 consultas do site comparadas linha por linha, antes e depois;
- cada tipo de clique comparado com a conta antiga.

## Os números

| | Antes | Depois |
|---|---|---|
| Medições que caíam | 13 de 16 | 0 de 16 |
| Tempo das que abriam | 10 a 19 s | menos de 2 s |
| Ficha de um produto, no banco | 170 ms (lia a base inteira) | 1 ms (lê só o produto) |

Um teste novo mede o tempo de cada aba nos dois perfis, inclusive a rajada de conexões frias, com limites que não
se sobem para passar. Ele entrou na bateria que roda no fim de cada sessão.
