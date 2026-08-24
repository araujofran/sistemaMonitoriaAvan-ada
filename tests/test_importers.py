from pathlib import Path

from app.database import batch_summary
from app.importers import load_source
from app.domain import Turn
from app.products import extract_attendant_from_turns, infer_product
from app.service import process_paths


def test_csv_unknown_columns_are_preserved(tmp_path: Path):
    path = tmp_path / "dynamic.csv"
    path.write_text(
        'COLUNA_NOVA;Produto Customizado;transcricao\n'
        'valor livre;Cartão Consignado;"#Cliente: Quero consultar meu cartão consignado.\n#Atendente: Vou verificar."\n',
        encoding="utf-8",
    )
    records = load_source(path)
    assert len(records) == 1
    assert records[0].metadata["COLUNA_NOVA"] == "valor livre"
    assert records[0].metadata["Produto Customizado"] == "Cartão Consignado"


def test_multiple_txt_files_become_multiple_interactions(tmp_path: Path):
    paths = []
    for number, product in enumerate(("cartão consignado", "veículo"), start=1):
        path = tmp_path / f"{number}.txt"
        path.write_text(f"#Cliente: Preciso de ajuda com {product}.\n#Atendente: Vou verificar.", encoding="utf-8")
        paths.append(path)
    result = process_paths(paths, "Múltiplos TXT")
    assert result["processed"] == 2
    assert result["failed"] == 0
    assert set(batch_summary(result["batch_id"])["products"]) == {"Cart\u00e3o Consignado", "Ve\u00edculos"}


def test_mojibake_product_is_normalized():
    product, source = infer_product({"ATENDENTE": "Ve�culos"}, "")
    assert product == "Ve\u00edculos"
    assert source == "metadata"


def test_attendant_is_extracted_only_from_explicit_self_presentation():
    turns = [Turn(1,"ATENDENTE","Bom dia, eu me chamo Haru. Como posso ajudar?","",0,50)]
    assert extract_attendant_from_turns(turns) == ("Haru", "eu me chamo Haru")
    false_positive = [Turn(1,"ATENDENTE","A informação que tenho aqui é que foi quitado.","",0,50)]
    assert extract_attendant_from_turns(false_positive) == ("Não identificado", "")


def test_xlsx_handle_is_released_after_read(tmp_path: Path):
    import pandas as pd
    path = tmp_path / "upload.xlsx"
    pd.DataFrame({"transcricao": ["#Cliente: Preciso de ajuda.\n#Atendente: Vou verificar."],
                  "produto": ["Câmbio"]}).to_excel(path, index=False)
    assert len(load_source(path)) == 1
    # This fails with WinError 32 on Windows if openpyxl still owns the file.
    path.unlink()
    assert not path.exists()
