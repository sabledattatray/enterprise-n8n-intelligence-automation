from data.generators.seed_generator import generate_dataset


def test_seed_reproducibility():
    """Verifies that two runs with the same seed yield bit-identical datasets."""
    records1, stats1 = generate_dataset(num_rows=50, seed=999)
    records2, stats2 = generate_dataset(num_rows=50, seed=999)

    assert stats1 == stats2
    assert len(records1) == len(records2)
    for r1, r2 in zip(records1, records2):
        assert r1 == r2


def test_defect_injections():
    """Verifies that controlled defects are injected according to specified rates."""
    records, stats = generate_dataset(
        num_rows=200,
        seed=123,
        duplicate_rate=0.05,
        negative_qty_rate=0.05,
        invalid_currency_rate=0.05,
        missing_fields_rate=0.05,
    )
    assert stats["total_records"] == 200
    assert stats["duplicates_injected"] > 0
    assert stats["negative_quantity_injected"] > 0
    assert stats["invalid_currency_injected"] > 0
    assert stats["missing_fields_injected"] > 0

