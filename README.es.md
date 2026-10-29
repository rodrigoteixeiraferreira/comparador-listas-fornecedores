# Comparador de listas de proveedores

[Português](README.md) · [English](README.en.md) · **Español**

[![pruebas](https://github.com/rodrigoteixeiraferreira/comparador-listas-fornecedores/actions/workflows/ci.yml/badge.svg)](https://github.com/rodrigoteixeiraferreira/comparador-listas-fornecedores/actions/workflows/ci.yml)

![Comparador de listas de proveedores: cero falsos positivos como criterio de aceptación](docs/img/capa_repositorio.png)

Un sistema que lee listas de precios de proveedores (planilla, PDF y foto), identifica cada línea en el catálogo de
un supermercado y dice, producto por producto, quién vende más barato. El criterio de aceptación fue uno solo:
**cero coincidencias confirmadas automáticamente donde marca, tamaño o unidad no coinciden.**

Este repositorio tiene dos partes:

- **el estudio de caso** del sistema que entregué a un supermercado de barrio en Argentina en octubre de 2026: el
  problema, las decisiones y los números. El código y los datos de ese proyecto son del cliente y no están acá;
- **una demo reescrita desde cero**, con datos ficticios, que corre y se prueba sola: el mismo diseño, un mundo
  inventado y una plantilla de respuestas para verificar cada decisión.

Las marcas, los proveedores, los precios y los códigos de barras de la demo son inventados. Las pantallas del
original que aparecen acá son réplicas con datos ficticios. Las imágenes y los documentos detallados están en
portugués.

## El problema

Un supermercado de barrio recibe decenas de listas de precios por mes, cada proveedor con su formato y sus
abreviaturas. El comprador había armado un comparador con un asistente de IA. El backup de ese sistema mostró dos
números:

- de 5.129 productos, solo 199 (3,9 %) tenían precio de dos o más proveedores;
- de los 475 pares que el sistema confirmó solo, **63 (13,3 %) tenían el tamaño equivocado**.

La causa era una sola: el sistema comparaba la similitud de las palabras, y el tamaño entraba como texto. Un paquete
de 1 kg coincidía con el de 2 kg con puntaje máximo, porque el nombre coincidía entero.

## La tesis

1. **Tamaño, unidad y marca son condición, no puntaje.** Si no coinciden, el par ni siquiera es candidato.
2. **La similitud de texto nunca confirma.** Solo ordena los candidatos para la revisión humana.
3. **La IA interpreta y ordena; la base calcula.** Ningún precio, cantidad o diferencia sale de un modelo: todo
   número es una consulta SQL, rastreable hasta la lista y la fecha de donde vino.
4. **La pendiente acumulada no es un defecto; el falso positivo sí.**

## Arquitectura

```mermaid
flowchart TD
    L["Lista del proveedor<br/>planilla, PDF o foto"] --> F{"¿Formato conocido?"}
    F -- sí --> A["Lector<br/>código"]
    F -- "foto" --> I["Dos lecturas de IA independientes<br/>solo sigue lo que las dos leen igual"]
    A --> P{"Portón<br/>7 controles"}
    I --> P
    P -- "no pasó" --> ANT["Vale la lista anterior"]
    P -- pasó --> E["Extractor de atributos<br/>marca, tipo, variedad, contenido, unidad"]
    E --> C["Cascada en SQL<br/>código de barras, código del proveedor,<br/>equivalencia confirmada, atributos"]
    C --> N["Par con nivel de certeza y motivo"]
    N --> W["Comparación de precios"]
    N -- "solo lo dudoso" --> H["Revisión humana"]
    H -- "graba el «es», el «no es» y el «la tienda no lo tiene»" --> AP["Aprendizaje"]
    AP --> C
    N --> AU["Auditoría por muestra"]
    AU -- "error arriba del 2 %" --> D["Ese tipo de decisión<br/>deja de decidir solo"]
```

| Capa | Tecnología |
|---|---|
| Base, reglas y cálculo | Postgres en Supabase: migraciones versionadas, funciones, vistas, RLS |
| Lectura de listas y extracción | Python (openpyxl, pdfplumber) |
| Lectura de foto | doble lectura por dos modelos distintos de Claude, con las respuestas grabadas |
| Pruebas | pytest; en GitHub Actions, contra el Supabase local en Docker |
| Desarrollo | Claude Code con el MCP de Supabase |

## La demo

Una semilla genera un mundo entero: el mercado (251 productos de 16 marcas inventadas), el catálogo de la tienda (158
productos), las listas de septiembre y octubre de dos proveedores (Mayorista Norte en planilla, sin IVA;
Distribuidora Andina en PDF, con IVA y abreviada) y la foto de una lista impresa de un tercero (Mercantil Ombú). El
generador planta trampas en lugares sorteados y escribe la **plantilla de respuestas** de cada línea: cuál es el
producto correcto, o ninguno. El sistema nunca lee la plantilla; solo las pruebas la leen.

Las trampas: 1 kg × 2 kg, marca cambiada, variedad cambiada, pack × unidad suelta, la palabra de más que hace otro
producto («SIN TACC»), la abreviatura que el vocabulario no conoce, el precio de la caja cerrada, el código de barras
de otro tamaño, el código del proveedor reutilizado para otro producto y el precio tipeado con un cero de más.

| Lo que la demo prueba | Resultado |
|---|---|
| Pares confirmados equivocados, verificados contra la plantilla | **0**, en 5 mundos (21 listas) |
| Listas arruinadas a propósito que el portón retiene en el control correcto | **51 de 51** |
| Listas buenas que el portón retiene | 0 de 20 |
| Preguntas al revisor el mes siguiente, después de responder las del mes anterior | menos de la mitad |
| La foto leída por dos modelos (Sonnet y Haiku) | 44 de 44 líneas iguales en las dos lecturas, y correctas |

La auditoría por muestra de la semilla 1 (el auditor de la demo responde con la plantilla):

| Tipo de decisión | Muestra | Errores | Error real, con 95 % de confianza | Decisión |
|---|---|---|---|---|
| código de barras | 50 | 0 | hasta 5,8 % | sigue activa |
| código del proveedor | 50 | 0 | hasta 5,8 % | sigue activa |
| atributos idénticos | 40 | 0 | hasta 7,2 % | sigue activa |
| similitud alta (en prueba) | 18 | 18 | — | **desactivada** |
| identidad con precio dudoso (en prueba) | 1 | 0 | hasta 95 % | sigue en prueba: una muestra chica no decide |

### Cómo correrla

```bash
python -m venv .venv && . .venv/bin/activate     # en Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m pricelists.world --seed 1              # el mundo de la semilla 1, en generated/seed-1
pytest                                           # sin base, las pruebas de base se saltean

supabase db start                                # Postgres local con las migraciones (necesita Docker)
export DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
pytest                                           # ahora con la prueba en la base
python -m pricelists.pipeline --seed 1           # carga, revisa, audita y muestra la cuenta de cada lista
```

### Qué hay dónde

| Dónde | Qué |
|---|---|
| `src/pricelists/world/` | el generador del mundo ficticio, de las listas, de la foto y de las corrupciones |
| `src/pricelists/extract.py` | el extractor de atributos: lo que no reconoce queda como «palabra que sobra», nunca se adivina |
| `src/pricelists/readers.py`, `ai_reader.py` | los lectores de planilla y PDF; la doble lectura de la foto |
| `src/pricelists/gate.py` | el portón de 7 controles |
| `supabase/migrations/` | el esquema, la cascada en SQL, las vistas y el RLS |
| `src/pricelists/audit.py` | la auditoría por muestra |
| `prompts/`, `data/recorded/` | el prompt de lectura de la foto y las dos lecturas grabadas |
| `tests/` | la prueba: generador, extractor, lectores, portón, cascada y auditoría |

### Los límites

- **El mundo y las reglas tienen el mismo autor.** Las trampas salen de semillas, hay escrituras que el vocabulario
  no conoce a propósito y la prueba corre en varios mundos; aun así, un mundo generado se porta mejor que las listas
  reales. El proyecto original se probó con las listas reales; esta demo prueba el mecanismo.
- **Los límites del portón** (variación de precio, precio contra costo, continuidad) están calibrados para este
  mundo.
- **La foto se leyó una vez** por dos subagentes de Claude Code, cada uno solo con la foto y el prompt, y las
  lecturas quedaron grabadas: la demo no llama a la API. En esta foto limpia las dos lecturas coincidieron en todo;
  la cola de discrepancias está probada por una prueba que planta divergencias.
- **El revisor y el auditor de la demo son simulados:** responden con la plantilla. En el original, respondió una
  persona.
- **El panel** (comparación, cola de revisión y estado de la base) es el próximo paso.

## Las decisiones que más pesaron

- **La palabra que sobra.** Sin código de barras, toda palabra que aparece de un solo lado tiene que ser ruido
  declarado en el vocabulario, o el par no confirma. En el original, la regla tiró abajo 365 pares que parecían
  correctos.
- **La decisión negativa es un dato.** El «no es este» del revisor vale en todos los pasos, incluso en el código de
  barras, y la oferta rechazada no vuelve. «La tienda no lo tiene» también es una decisión: la línea no vuelve a
  revisión.
- **Todo par tiene nivel y motivo:** 1 decisión humana, 2 código de barras, 3 regla fuerte, 4 en revisión. Solo los
  niveles 1 a 3 cuentan como confirmados; el par en revisión nunca gana la comparación callado.
- **Identidad y precio son dos preguntas.** El precio muy lejos del costo no deshace la identificación: el producto
  sigue identificado y esa línea solo no compite hasta que alguien revise el precio.
- **La lista nueva espera en el portón.** Siete controles antes de reemplazar a la anterior. Mientras no pasa, vale
  la anterior.
- **La máquina tiene una tasa de error medida.** Por muestra sorteada, por tipo de decisión, con un límite de 2 %.

Los detalles del original están en [`docs/`](docs/), en portugués.

## Resultados del proyecto original

En menos de cuatro semanas, de la base al panel:

| Medida | Valor |
|---|---|
| Pares confirmados con marca, tamaño o unidad incompatible | **0**, en todas las rondas de control |
| Productos vendidos con proveedor identificado | 3.002 de 4.353 (69 %) |
| Productos con precio de dos o más proveedores | 1.596 (en el sistema anterior, 199) |
| Listas leídas | 88, de planilla, PDF y foto |
| Error de la IA en los pares confirmados, por muestra | 1 en 145 (0,7 %); hasta 3 % con 95 % de confianza |
| Proveedor desconocido (prueba ciega) | 0 pares equivocados; 0 a 4 ítems por 100 líneas en la mesa del comprador |
| Tiempo de apertura de las pantallas | de 10 a 19 s (o error) a menos de 2 s |

### Pantallas del original

Réplicas fieles al diseño del panel, con datos ficticios.

![Réplica del estado de la base](docs/img/tela_estado_replica.png)

![Réplica de la comparación de precios](docs/img/tela_comparacao_replica.png)

## Cómo trabajé

- **Un documento de reglas vigentes**, leído entero antes de cualquier propuesta. Una decisión tomada con datos
  reales no se vuelve a discutir sin pedido.
- **Cada sesión abre con un brief y cierra con un informe**, un índice de versiones y la limpieza de los archivos
  superados.
- **Una batería de pruebas al final de cada sesión.** Las pruebas no escriben en la base real.
- **Migración probada en una copia** antes de la base real; una migración aplicada no se edita.
- **Costo de la IA medido**, con un tope mensual.

## Contacto

Rodrigo Teixeira Ferreira — automatización, datos y agentes de IA. Abierto a contratos y a puestos fijos.
[LinkedIn](https://www.linkedin.com/in/rodrigo-teixeira-ferreira-2b00a31b6/) · [flechamedicina@gmail.com](mailto:flechamedicina@gmail.com) · [GitHub](https://github.com/rodrigoteixeiraferreira)
