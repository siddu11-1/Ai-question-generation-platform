"""
=============================================================================
utils/bulk_import.py
Description:
    Allows trainers to bulk-import questions from a CSV file
    into any question bank — bypassing GPT for pre-existing content.

Expected CSV columns:
    question_text, option_a, option_b, option_c, option_d,
    correct_option, difficulty, explanation (optional)

Usage in trainer_page.py:
    from utils.bulk_import import import_questions_from_csv, get_csv_template
=============================================================================
"""

import io
import pandas as pd
from database.questions_db import insert_question


# Required CSV columns (explanation is optional)
REQUIRED_COLS = ["question_text", "option_a", "option_b", "option_c", "option_d",
                 "correct_option", "difficulty"]


def get_csv_template() -> bytes:
    """
    Returns a sample CSV template as bytes for trainers to download.
    Shows the exact column format expected.
    """
    sample = pd.DataFrame([
        {
            "question_text": "What is the time complexity of binary search?",
            "option_a":      "O(n)",
            "option_b":      "O(log n)",
            "option_c":      "O(n²)",
            "option_d":      "O(1)",
            "correct_option":"B",
            "difficulty":    "moderate",
            "explanation":   "Binary search halves the search space each step → O(log n)"
        },
        {
            "question_text": "Which data structure uses LIFO order?",
            "option_a":      "Queue",
            "option_b":      "Array",
            "option_c":      "Stack",
            "option_d":      "Linked List",
            "correct_option":"C",
            "difficulty":    "easy",
            "explanation":   "Stack uses Last-In-First-Out (LIFO) ordering."
        }
    ])
    return sample.to_csv(index=False).encode("utf-8")


def import_questions_from_csv(uploaded_file, bank_id: int) -> dict:
    """
    Reads a CSV file and bulk-inserts all valid questions into the database.

    Args:
        uploaded_file : Streamlit UploadedFile object (.csv)
        bank_id       : Target question bank ID

    Returns:
        Dict with keys:
            'success'  : int — number of questions imported successfully
            'failed'   : int — number of rows skipped due to errors
            'errors'   : list of str — error messages per failed row
    """
    result = {"success": 0, "failed": 0, "errors": []}

    try:
        df = pd.read_csv(uploaded_file)
    except Exception as e:
        result["errors"].append(f"Could not read CSV: {e}")
        result["failed"] += 1
        return result

    # Check required columns exist
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        result["errors"].append(f"Missing required columns: {missing}")
        result["failed"] = len(df)
        return result

    for idx, row in df.iterrows():
        try:
            # Validate correct_option
            correct = str(row["correct_option"]).strip().upper()
            if correct not in ["A", "B", "C", "D"]:
                raise ValueError(f"correct_option must be A/B/C/D, got '{correct}'")

            # Validate difficulty
            diff = str(row["difficulty"]).strip().lower()
            if diff not in ["easy", "moderate", "hard"]:
                diff = "moderate"   # Default to moderate if invalid

            insert_question(
                bank_id        = bank_id,
                question_text  = str(row["question_text"]).strip(),
                option_a       = str(row["option_a"]).strip(),
                option_b       = str(row["option_b"]).strip(),
                option_c       = str(row["option_c"]).strip(),
                option_d       = str(row["option_d"]).strip(),
                correct_option = correct,
                difficulty     = diff,
                explanation    = str(row.get("explanation", "")).strip()
            )
            result["success"] += 1

        except Exception as e:
            result["failed"] += 1
            result["errors"].append(f"Row {idx + 2}: {e}")

    return result
