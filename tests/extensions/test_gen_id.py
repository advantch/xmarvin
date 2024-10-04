import multiprocessing
import time
from collections import Counter

from marvin.extensions.utilities.generate_id import generate_id


def generate_ids(num_ids, prefix):
    return [generate_id(prefix) for _ in range(num_ids)]


def stress_test(total_ids, num_processes, prefix):
    ids_per_process = total_ids // num_processes

    with multiprocessing.Pool(processes=num_processes) as pool:
        results = pool.starmap(
            generate_ids, [(ids_per_process, prefix)] * num_processes
        )

    all_ids = [id for sublist in results for id in sublist]

    # Check for duplicates
    duplicates = [item for item, count in Counter(all_ids).items() if count > 1]

    return len(all_ids), len(duplicates)


def timing_test(prefix, num_iterations=1000):
    start_time = time.time()
    for _ in range(num_iterations):
        generate_id(prefix)
    end_time = time.time()
    return end_time - start_time


def test_generate_id():
    total_ids = 1_000  # Total number of IDs to generate
    num_processes = multiprocessing.cpu_count()  # Use all available CPU cores
    prefix = "test"

    total_generated, num_duplicates = stress_test(total_ids, num_processes, prefix)

    results = {
        "total_generated": total_generated,
        "num_duplicates": num_duplicates,
    }
    assert results["num_duplicates"] == 0, results
