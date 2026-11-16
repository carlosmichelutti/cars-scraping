# cars-scraping

Scraper em Python com Playwright para o [catálogo de demonstração do Web Scraper](https://webscraper.io/test-sites/pagination). Execute a partir da raiz do projeto com o `uv`. Na primeira execução, o script baixa o Chromium do Playwright se for necessário.

```powershell
# Catálogo geral em data/cars.csv, com o navegador visível
uv run scripts/cars_scraping.py

# Um CSV para cada marca do menu lateral, sem janela
uv run scripts/cars_scraping.py --extraction-mode brands --headless

# Apenas data/bmw.csv
uv run scripts/cars_scraping.py --extraction-mode brands --brand BMW
```

`--headless` oculta a janela. Sem essa opção, ou com `--no-headless`, o Chromium abre em modo visível. O argumento `--brand` aceita o nome da marca independentemente de maiúsculas e minúsculas.

O CSV usa quilometragem em km (`mileage_km`), preço em dólares americanos (`price_usd`) e contagem de estrelas preenchidas (`rating`). O campo `status` preserva os valores `Available`, `Reserved` e `Sold` do catálogo. A coluna `available_quantity` fica vazia para reservas e vendas.
