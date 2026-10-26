# bu_v2.asn1 — especificação ASN.1 do Boletim de Urna (versão 2)

Origem: pacote oficial do TSE "Formato dos arquivos de BU, RDV e assinatura digital" (v2, 2024),
que o site www.tse.jus.br não deixa baixar de forma automatizada (HTTP 403).

Como não foi possível baixar o zip oficial, o arquivo veio de cópias públicas do pacote:

| Repositório | Caminho | SHA-256 |
|---|---|---|
| github.com/alissonlinneker/DataUrnas-BR | spec/v2/bu.asn1 | e53e28e9812bb7e19cc4bcc77b6ce48f25c413f62a60369a91c4f269e19b7ed6 |
| github.com/doccaz/urnas-br | docv2/spec/bu.asn1 | e53e28e9812bb7e19cc4bcc77b6ce48f25c413f62a60369a91c4f269e19b7ed6 |

As duas cópias independentes são idênticas byte a byte. A versão 1 (2022) não decodifica os BUs
de 2026; a v2 decodifica. Validação funcional: a soma dos BUs decodificados do DF (2º turno de 2026)
tem de bater voto a voto com a totalização oficial da API de resultados (tests/test_bu.py).

Se o zip oficial for obtido, comparar o hash de spec/bu.asn1 com o acima e substituir esta nota.
