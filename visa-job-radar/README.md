# Visa Job Radar

Personal high-recall visa-job monitor for Amit's backend/software-engineering search.

Targets: Australia, New Zealand, UAE (Dubai/Abu Dhabi), all Europe, UK/Britain, Ireland, Canada and the United States.

The matcher evaluates the job description and technical skills instead of requiring an exact job title. Missing experience or visa information is treated as unknown, not as an automatic rejection.

The GitHub Actions workflow refreshes the data every 6 hours. The root `index.html` is the dashboard entry point.

Never commit credentials. Telegram uses GitHub Actions Secrets if enabled.
