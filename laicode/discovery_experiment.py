"""A3-D task population and its frozen training/held-out split.

This module exists to be committed *before* anything discovers, which is rule
R2 in the charter. Its whole job is to fix the question before the answer is
visible.

The population is defined by one stated principle rather than by picking tasks
that suit the learner: every task is a single pass over an `i64` array with a
scalar target, expressible as `acc = f(acc, element, target)` per element
starting from `acc = 0`. Membership is decided by that shape alone. No task is
labelled with the abstraction it "needs", because that labelling is exactly what
made the A2-S study circular -- it chose treatment tasks *because* they required
the vocabulary it then supplied.

The split is a deterministic permutation under a committed seed, not a hand
assignment. Discovery sees the training half only. Whether anything it finds
helps the held-out half is then a fact about the learner rather than a fact
about how the halves were drawn, and the study is free to fail: a split can
easily leave the training half with no shared structure at all, which is
falsifier F1 firing legitimately.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from .canonical import JsonValue, content_id


SPLIT_SCHEMA_VERSION = "DiscoveryTaskSplitV3"
REGISTERED_SPLIT_SEED = "a3d-split-v1"
REGISTERED_AT = "2026-08-05T00:00:00Z"
TRAINING_SHARE = 7

Oracle = Callable[[Sequence[int], int], int]


def _sum_all(nums: Sequence[int], target: int) -> int:
    del target
    return sum(nums)


def _count_all(nums: Sequence[int], target: int) -> int:
    del target
    return len(nums)


def _sum_shifted(nums: Sequence[int], target: int) -> int:
    return sum(value + target for value in nums)


def _max_element(nums: Sequence[int], target: int) -> int:
    del target
    return max([*nums, 0])


def _max_shifted(nums: Sequence[int], target: int) -> int:
    return max([value + target for value in nums] + [0])


def _min_element(nums: Sequence[int], target: int) -> int:
    del target
    return min([*nums, 0])


def _count_greater_than_target(nums: Sequence[int], target: int) -> int:
    return sum(1 for value in nums if value > target)


def _count_less_than_target(nums: Sequence[int], target: int) -> int:
    return sum(1 for value in nums if value < target)


def _count_equal_to_target(nums: Sequence[int], target: int) -> int:
    return sum(1 for value in nums if value == target)


def _sum_greater_than_target(nums: Sequence[int], target: int) -> int:
    return sum(value for value in nums if value > target)


def _sum_less_than_target(nums: Sequence[int], target: int) -> int:
    return sum(value for value in nums if value < target)


def _sum_positive_part(nums: Sequence[int], target: int) -> int:
    del target
    return sum(value for value in nums if value > 0)


def _count_non_negative(nums: Sequence[int], target: int) -> int:
    del target
    return sum(1 for value in nums if value >= 0)


def _sum_absolute_deviation(nums: Sequence[int], target: int) -> int:
    return sum(abs(value - target) for value in nums)


@dataclass(frozen=True)
class DiscoveryTask:
    task_id: str
    description: str
    oracle: Oracle

    def to_document(self) -> dict[str, JsonValue]:
        return {"task_id": self.task_id, "description": self.description}


def registered_discovery_tasks() -> tuple[DiscoveryTask, ...]:
    """The frozen population.

    `sum_absolute_deviation` is deliberately included even though it is not
    expressible as a single guarded assignment over add/sub, so it is very
    likely unreachable by either arm. A population containing only tasks the
    machinery can already reach cannot produce a negative result.
    """

    return (
        DiscoveryTask("sum_all", "total of the input", _sum_all),
        DiscoveryTask("count_all", "number of input elements", _count_all),
        DiscoveryTask("sum_shifted", "total with the target added per element", _sum_shifted),
        DiscoveryTask("max_element", "largest element, floored at zero", _max_element),
        DiscoveryTask("max_shifted", "largest shifted element, floored at zero", _max_shifted),
        DiscoveryTask("min_element", "smallest element, capped at zero", _min_element),
        DiscoveryTask("count_greater_than_target", "elements above the target", _count_greater_than_target),
        DiscoveryTask("count_less_than_target", "elements below the target", _count_less_than_target),
        DiscoveryTask("count_equal_to_target", "elements equal to the target", _count_equal_to_target),
        DiscoveryTask("sum_greater_than_target", "total of elements above the target", _sum_greater_than_target),
        DiscoveryTask("sum_less_than_target", "total of elements below the target", _sum_less_than_target),
        DiscoveryTask("sum_positive_part", "total of the positive elements", _sum_positive_part),
        DiscoveryTask("count_non_negative", "elements that are not negative", _count_non_negative),
        DiscoveryTask("sum_absolute_deviation", "total distance from every element to the target", _sum_absolute_deviation),
    )


def _permutation_key(task_id: str) -> str:
    """Seeded, replayable ordering key.

    Deriving the key from the committed seed and the task identity keeps the
    permutation reproducible from the repository alone -- no stored random
    state, and no way to reroll a split quietly.
    """

    return content_id({
        "schema_version": SPLIT_SCHEMA_VERSION,
        "seed": REGISTERED_SPLIT_SEED,
        "task_id": task_id,
    })


def frozen_split() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return `(training_task_ids, heldout_task_ids)`."""

    ordered = sorted(
        (task.task_id for task in registered_discovery_tasks()),
        key=_permutation_key,
    )
    return tuple(ordered[:TRAINING_SHARE]), tuple(ordered[TRAINING_SHARE:])


def split_manifest() -> dict[str, JsonValue]:
    training, heldout = frozen_split()
    return {
        "schema_version": SPLIT_SCHEMA_VERSION,
        "experiment_name": "abstraction-discovery-transfer-a3d-v1",
        "question": "does an abstraction discovered from synthesized training programs reduce search cost on unseen tasks",
        "registered_at": REGISTERED_AT,
        "seed": REGISTERED_SPLIT_SEED,
        "population_rule": "single_pass_fold_over_i64_array_with_scalar_target",
        "assignment_rule": "deterministic_permutation_under_committed_seed_not_hand_assignment",
        "labelling_rule": "no_task_is_labelled_with_the_abstraction_it_requires",
        "tasks": [task.to_document() for task in registered_discovery_tasks()],
        "training_task_ids": list(training),
        "heldout_task_ids": list(heldout),
        "falsifiers": [
            "F1_no_valid_abstraction_is_discovered_from_the_training_half",
            "F2_abstractions_are_discovered_but_do_not_reduce_heldout_search_cost",
            "F3_discovery_only_recovers_shapes_the_heldout_half_was_chosen_to_need",
        ],
    }


def split_id() -> str:
    """Content identity of the frozen split.

    `tests/test_discovery_experiment.py` asserts this against a literal, so the
    population or the seed cannot change after a result exists without the
    change being visible in a diff.
    """

    return content_id(split_manifest())
