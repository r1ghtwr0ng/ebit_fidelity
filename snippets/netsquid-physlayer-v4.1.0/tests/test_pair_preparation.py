import unittest
import numpy as np

from netsquid_physlayer.pair_preparation import PairPreparation, ExcitedPairPreparation
from netsquid.qubits.qubitapi import fidelity


class WrongSubclassingPP(PairPreparation):
    def gen(self):
        pass


class CorrectSubclassingPP(PairPreparation):
    def generate(self, *args, **kwargs):
        pass


class TestAbstractClasses(unittest.TestCase):
    def test_init(self):
        with self.assertRaises(TypeError):
            PairPreparation()
        with self.assertRaises(TypeError):
            WrongSubclassingPP()
        CorrectSubclassingPP()


class TestExcitedPairPreparation(unittest.TestCase):
    def test_generate(self):
        pair_prep = ExcitedPairPreparation()

        with self.assertRaises(TypeError):
            pair_prep.generate()
        with self.assertRaises(TypeError):
            pair_prep.generate(a=0.5)
        with self.assertRaises(ValueError):
            pair_prep.generate(alpha=-1)
        with self.assertRaises(ValueError):
            pair_prep.generate(alpha=2)

        # alpha = 0
        (spin, photon) = pair_prep.generate(alpha=0)
        F = fidelity([spin, photon], np.array([[1], [0], [0], [0]]))

        self.assertAlmostEqual(F, 1)

        # alpha = 0.5
        (spin, photon) = pair_prep.generate(alpha=0.5)
        F = fidelity([spin, photon], np.array([[1 / np.sqrt(2)], [0], [0], [1 / np.sqrt(2)]]))

        self.assertAlmostEqual(F, 1)


if __name__ == "__main__":
    unittest.main()
