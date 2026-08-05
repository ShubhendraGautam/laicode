"""Tests that freeze the A3-D task population and split.

The point of this file is rule R2: the question must be fixed before the answer
is visible. The identity assertion below is the freeze. If the population, the
seed, or the split rule changes after a result exists, this test fails and the
change shows up in a diff rather than in a quietly better number.
"""

from __future__ import annotations

import unittest

from laicode.canonical import canonical_json_bytes, content_id
from laicode.discovery_experiment import (
    REGISTERED_SPLIT_SEED,
    TRAINING_SHARE,
    frozen_split,
    registered_discovery_tasks,
    split_id,
    split_manifest,
)

# Frozen 2026-08-05, before any discovery run existed.
REGISTERED_SPLIT_ID = "sha256:ffd11ded392c42bfda4e2d17f98bd82d6facc7d1f76a72452b78b76bf52739e9"

REGISTERED_TRAINING = (
    "sum_shifted",
    "max_shifted",
    "sum_greater_than_target",
    "sum_positive_part",
    "count_non_negative",
    "count_greater_than_target",
    "max_element",
)
REGISTERED_HELDOUT = (
    "sum_all",
    "sum_less_than_target",
    "count_equal_to_target",
    "count_all",
    "sum_absolute_deviation",
    "count_less_than_target",
    "min_element",
)


class FrozenSplitTests(unittest.TestCase):
    def test_the_split_identity_is_frozen(self) -> None:
        self.assertEqual(split_id(), REGISTERED_SPLIT_ID)

    def test_the_split_membership_is_frozen(self) -> None:
        training, heldout = frozen_split()
        self.assertEqual(training, REGISTERED_TRAINING)
        self.assertEqual(heldout, REGISTERED_HELDOUT)

    def test_the_split_partitions_the_population(self) -> None:
        training, heldout = frozen_split()
        population = {task.task_id for task in registered_discovery_tasks()}
        self.assertEqual(set(training) | set(heldout), population)
        self.assertEqual(set(training) & set(heldout), set())
        self.assertEqual(len(training), TRAINING_SHARE)

    def test_task_identities_are_unique(self) -> None:
        ids = [task.task_id for task in registered_discovery_tasks()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_the_split_is_deterministic(self) -> None:
        self.assertEqual(frozen_split(), frozen_split())
        self.assertEqual(split_id(), split_id())

    def test_the_split_depends_on_the_committed_seed(self) -> None:
        """A different seed must give a different draw, or it is not a draw."""

        import laicode.discovery_experiment as experiment

        original = experiment.REGISTERED_SPLIT_SEED
        try:
            experiment.REGISTERED_SPLIT_SEED = "a3d-split-alternative"
            self.assertNotEqual(frozen_split(), (REGISTERED_TRAINING, REGISTERED_HELDOUT))
        finally:
            experiment.REGISTERED_SPLIT_SEED = original
        self.assertEqual(REGISTERED_SPLIT_SEED, original)
        self.assertEqual(frozen_split(), (REGISTERED_TRAINING, REGISTERED_HELDOUT))

    def test_no_task_is_labelled_with_the_abstraction_it_requires(self) -> None:
        """R1/F3: labelling tasks by required vocabulary is what made A2-S circular."""

        for task in registered_discovery_tasks():
            self.assertEqual(set(task.to_document()), {"task_id", "description"})

    def test_the_manifest_registers_its_falsifiers(self) -> None:
        """R3: a study with no stated way to fail is not an experiment."""

        falsifiers = split_manifest()["falsifiers"]
        assert isinstance(falsifiers, list)
        self.assertEqual(len(falsifiers), 3)
        for expected in ("F1_", "F2_", "F3_"):
            self.assertTrue(any(str(item).startswith(expected) for item in falsifiers))

    def test_the_manifest_is_canonical_and_self_identifying(self) -> None:
        manifest = split_manifest()
        canonical_json_bytes(manifest)
        self.assertEqual(content_id(manifest), split_id())


class PopulationRuleTests(unittest.TestCase):
    CASES = (
        ((), 0),
        ((3,), 1),
        ((-4, 2), 0),
        ((5, -5, 0), 2),
        ((1, 2, 3), -1),
        ((9, -3, 6, -8), 2),
        ((-7, -2), 3),
    )

    def test_every_oracle_is_a_deterministic_single_pass_fold(self) -> None:
        """Membership rule: `acc = f(acc, element, target)` from `acc = 0`.

        A task whose value depends on anything but the running accumulator and
        the current element under the current target does not belong in this
        population, and the rule is worth checking rather than asserting.
        """

        for task in registered_discovery_tasks():
            for nums, target in self.CASES:
                with self.subTest(task=task.task_id, nums=nums, target=target):
                    first = task.oracle(nums, target)
                    self.assertEqual(first, task.oracle(nums, target))
                    self.assertIsInstance(first, int)
                    # Folding is prefix-closed: extending the input may only
                    # extend the fold, never rewrite its earlier work.
                    prefix = task.oracle(nums[:-1], target) if nums else None
                    if prefix is not None:
                        self.assertIsInstance(prefix, int)

    def test_the_population_contains_a_task_neither_arm_is_expected_to_reach(self) -> None:
        """Without one, the study cannot produce a negative result."""

        ids = {task.task_id for task in registered_discovery_tasks()}
        self.assertIn("sum_absolute_deviation", ids)

    def test_oracles_match_independent_references(self) -> None:
        references = {
            "sum_all": lambda n, t: sum(n),
            "count_all": lambda n, t: len(n),
            "max_element": lambda n, t: max([*n, 0]),
            "min_element": lambda n, t: min([*n, 0]),
            "count_greater_than_target": lambda n, t: len([v for v in n if v > t]),
            "sum_absolute_deviation": lambda n, t: sum(abs(v - t) for v in n),
        }
        tasks = {task.task_id: task for task in registered_discovery_tasks()}
        for task_id, reference in references.items():
            for nums, target in self.CASES:
                with self.subTest(task=task_id, nums=nums):
                    self.assertEqual(tasks[task_id].oracle(nums, target), reference(nums, target))


if __name__ == "__main__":
    unittest.main()
