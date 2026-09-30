import json
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision

def run_benchmark():
    with open("eval/test_dataset.json") as f:
        data = json.load(f)

    eval_dict = {
        "question": [item["question"] for item in data],
        "contexts": [item["contexts"] for item in data],
        "answer": [item["answer"] for item in data],
        "ground_truth": [item["ground_truth"] for item in data]
    }

    dataset = Dataset.from_dict(eval_dict)
    print("Executing LLMOps evaluation across Ragas metrics...")
    results = evaluate(dataset, metrics=[faithfulness, answer_relevancy, context_precision])
    print("\n=== BENCHMARK REPORT ===")
    print(results)

if __name__ == "__main__":
    run_benchmark()
