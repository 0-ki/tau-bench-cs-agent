"""litellm 가격표에 없는 모델의 단가 등록. tau2 비용 집계(completion_cost)가 이 값을 쓴다."""

# USD / 1M tokens: (input, output, cached input, cache write 30m)
# 12h cache write 단가는 litellm에 대응 필드가 없어 기록만 한다.
PRICES_PER_MTOK = {
    "gpt-6-astra": (10.00, 50.00, 1.00, 12.50),  # 12h write 25.00
    "gpt-6.1-sol": (2.00, 10.00, 0.10, 2.50),  # 12h write 5.00
    "gpt-6.1-terra": (1.00, 5.00, 0.05, 1.25),  # 12h write 2.50
    "gpt-6-luna": (0.10, 0.50, 0.01, 0.125),  # 12h write 0.25
}


def register_prices() -> None:
    import litellm

    entries = {}
    for model, (inp, out, cached, write) in PRICES_PER_MTOK.items():
        entry = {
            "litellm_provider": "openai",
            "mode": "chat",
            "input_cost_per_token": inp / 1e6,
            "output_cost_per_token": out / 1e6,
            "cache_read_input_token_cost": cached / 1e6,
            "cache_creation_input_token_cost": write / 1e6,
        }
        # 응답의 model 필드는 접두사 없이 오는 경우가 많아 둘 다 등록
        entries[model] = entry
        entries[f"openai/{model}"] = entry
    litellm.register_model(entries)
