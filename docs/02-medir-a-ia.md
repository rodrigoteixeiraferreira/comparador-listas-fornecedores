# 2. Medir a IA por amostra

Antes de o revisor abrir um cartão de dúvida, a IA já o leu e deixou uma decisão com o porquê: «é este», «não é»,
«dúvida» ou «vale para vários». Foram dezenas de milhares de linhas.

«Nenhum erro em 26 mil decisões» não é uma taxa. É só o que ninguém conferiu.

<img src="img/medir_a_ia.png" width="420" alt="145 pares revisados, 1 erro">

## O método

1. **Regras escritas antes da primeira decisão**, e que não mudam durante a passada.
2. **Amostra aleatória estratificada** por tipo de decisão, sorteada com semente fixa e congelada antes de qualquer
   resposta. 463 decisões, de cinco tipos: o par confirmado, o par de um sabor que a lista não separa, o par de
   tamanho desatualizado no cadastro, a recusa (por motivo) e a associação automática do nível 4.
3. **Uma pessoa responde todas**, numa tela própria, pelo teclado. Levou menos de seis horas.
4. **A taxa é por tipo**, não geral.

## O resultado

- 1 erro em 145 nos pares confirmados (0,7%); nenhum nos outros tipos.
- Com 95% de confiança, o erro do par confirmado não passa de 3%, e o da recusa, de 1,8%.

## A regra que saiu disso

Um tipo de decisão **para de gravar sozinho quando a taxa observada passa de 2%**, isto é, quando há erro de
verdade. O limite largo de uma amostra pequena não desliga nada.

Dois efeitos:

- **A amostra promove.** A associação automática do nível 4 teve 150 revisados e nenhum erro. A regra combinada
  antes do sorteio mandava promover: 1.346 pares subiram ao nível 3, com o motivo escrito («confirmado por amostra:
  0 erros em 150»).
- **A amostra desliga.** Uma passada escrita em Python, sem IA, errou 2 de 7 e deixou de gravar sozinha.

## O que o erro ensinou

O único erro foi uma apresentação de presente (a caixa) que a regra tratava como embalagem que o cadastro não
escreve. Virou regra nova, com teste. Os comentários do revisor nos acertos também viraram propostas: de vocabulário,
de leitura e de preço.

## A leitura de fotos

A mesma lógica vale para o leitor de IA: duas leituras independentes, em contextos separados, e só segue o que as
duas dizem igual. Contra o gabarito de seis listas, 157 de 166 linhas saíram iguais nas duas leituras e certas,
nenhuma com preço errado. As 9 restantes eram as que uma leitura marcou com dúvida, e iriam à fila de suporte.
