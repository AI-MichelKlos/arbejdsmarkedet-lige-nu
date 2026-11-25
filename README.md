# Arbejdsmarkedet lige nu

Analytisk overblik over arbejdsmarkedet. [Åbn dashboardet](https://ai-michelklos.github.io/arbejdsmarkedet-lige-nu/) · [Del med ikon](https://ai-michelklos.github.io/arbejdsmarkedet-lige-nu/del/)

## Dataopdatering

GitHub Actions henter data på hverdage kl. 10.35 UTC. Arbejdsgangen **Opdater arbejdsmarkedstal** kan også startes manuelt fra Actions. Den kræver ingen særskilt API-nøgle. De 13 figurer bruger Jobindsats' offentlige databank, Statistikbankens API og Eurostats API. Kommunesammenligningen henter AUS08 direkte fra Statistikbanken ved valg af kommune.

Månedstal vises for den senest tilgængelige måned pr. figur. Landene i den internationale sammenligning bruger den seneste fælles måned. Manglende observationer giver huller i tidsserierne. Nye perioder og revisioner opdaterer både graf, nøgletal og tabel. Hvis en kilde fejler, beholder siden den senest publicerede version.

## Kør lokalt

Brug Python 3.11 eller nyere og Node.js 24. Kør fra projektets rod.

```sh
npm ci --ignore-scripts
python3 scripts/collect.py /tmp/arbejdsmarkedstal
node scripts/render.cjs index.html /tmp/arbejdsmarkedstal /tmp/arbejdsmarkedet.html
```

Hver figur har et direkte kildelink. Tabelvalg og beregninger findes i `scripts/sources.py`.
