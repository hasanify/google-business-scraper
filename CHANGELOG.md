# Changelog

All notable changes to Google Business Scraper will be documented in this file.

# [1.7.0](https://github.com/hasanify/google-business-scraper/compare/v1.6.0...v1.7.0) (2026-10-27)


### Bug Fixes

* **scraper:** resolve f-string backslash syntax error for python 3.11 compatibility ([3d86dd4](https://github.com/hasanify/google-business-scraper/commit/3d86dd45680fb94f41bede841de939c0b43bb89b))


### Features

* **scraper:** add standalone deduplication and AI enrichment CLI ([117f29e](https://github.com/hasanify/google-business-scraper/commit/117f29e662c713c88a230e368b6a5603c0fa6d14))

# Changelog

All notable changes to Google Business Scraper will be documented in this file.

# [1.6.0](https://github.com/hasanify/google-business-scraper/compare/v1.5.0...v1.6.0) (2026-10-26)


### Features

* **gui:** add interactive location selection and manual location entry ([aaebad3](https://github.com/hasanify/google-business-scraper/commit/aaebad3900a41faf4a5431bf87ae67652cac93a6))

# Changelog

All notable changes to Google Business Scraper will be documented in this file.

# [1.5.0](https://github.com/hasanify/google-business-scraper/compare/v1.4.0...v1.5.0) (2026-10-26)


### Features

* **gui:** add AWS Bedrock config card to dashboard ([a0b0e00](https://github.com/hasanify/google-business-scraper/commit/a0b0e00496639d7fa4a85c14d122e19f36014e6b))
* **gui:** simplify interface with 2-tab light mode and plain English text ([2478de3](https://github.com/hasanify/google-business-scraper/commit/2478de3fb69be0c80a6f64b0918b4f7951816eed)), closes [hi#contrast](https://github.com/hi/issues/contrast)

# Changelog

All notable changes to Google Business Scraper will be documented in this file.

# [1.4.0](https://github.com/hasanify/google-business-scraper/compare/v1.3.0...v1.4.0) (2026-10-26)


### Features

* **formatters:** add formatted_distance to dedup CSV ([e501650](https://github.com/hasanify/google-business-scraper/commit/e5016506370e424f2f565a9cd65d437bf3045939))


### Performance Improvements

* **enricher:** optimize AI token usage and caching ([4629c73](https://github.com/hasanify/google-business-scraper/commit/4629c7305fbf29268fb68f59d68078f08827064b))

# Changelog

All notable changes to Google Business Scraper will be documented in this file.

# [1.3.0](https://github.com/hasanify/google-business-scraper/compare/v1.2.4...v1.3.0) (2026-10-26)


### Features

* **scraper:** add Bedrock enrichment and dedup cleanup ([1ddd9e5](https://github.com/hasanify/google-business-scraper/commit/1ddd9e5cb8de47c114c99560ba0ebe17c6a996ec))
* **scraper:** prioritize WhatsApp numbers in dedup ([e1232fd](https://github.com/hasanify/google-business-scraper/commit/e1232fdc8ad60b88970207df77605bd3c63929a4))

# Changelog

All notable changes to Google Business Scraper will be documented in this file.

## [1.2.4](https://github.com/hasanify/google-business-scraper/compare/v1.2.3...v1.2.4) (2026-10-16)


### Bug Fixes

* **gui:** dynamically display app version from release tag ([aa02eed](https://github.com/hasanify/google-business-scraper/commit/aa02eed13beb9515cf29c7cedc7b4c44759516c4))

# Changelog

All notable changes to Google Business Scraper will be documented in this file.

## [1.2.3] - 2026-10-16

### Documentation
* **readme:** add tag column to output csv schema ([`88a303a`](https://github.com/hasanify/google-business-scraper/commit/88a303a))

## [1.2.2] - 2026-10-16

### Refactor
* rename project to Google Business Scraper ([`d83c3e6`](https://github.com/hasanify/google-business-scraper/commit/d83c3e6))

## [1.2.1] - 2026-10-16

### Build & Packaging
* add workflow to build and create release with tag on each commit ([`87d80c9`](https://github.com/hasanify/google-business-scraper/commit/87d80c9))
* add PyInstaller and documentation ([`c7d8b0d`](https://github.com/hasanify/google-business-scraper/commit/c7d8b0d))

## [1.2.0] - 2026-10-16

### Features
* **gui:** add desktop GUI and scraper engine hooks ([`e8bab1a`](https://github.com/hasanify/google-business-scraper/commit/e8bab1a))
* **scraper:** sanitize text fields and add utf-8-sig export ([`81e8211`](https://github.com/hasanify/google-business-scraper/commit/81e8211))
* **scraper:** support dual csv variants generation ([`80fd41c`](https://github.com/hasanify/google-business-scraper/commit/80fd41c))
* **scraper:** add lowercase slug tag column to csv ([`7a1c6c0`](https://github.com/hasanify/google-business-scraper/commit/7a1c6c0))
