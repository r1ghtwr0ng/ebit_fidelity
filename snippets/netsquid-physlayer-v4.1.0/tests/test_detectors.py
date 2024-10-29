"""Unit tests for three QuantumDetector subclasses."""
import numpy as np
import unittest

from netsquid.components.qdetector import QuantumDetectorError
from netsquid.qubits import qubitapi as qapi
from netsquid.qubits import operators as ops
from netsquid.qubits.ketstates import BellIndex, b01, b11
from netsquid.util.simlog import logger
from netsquid.util.simtools import sim_run, sim_reset

from netsquid_physlayer.detectors import TwinDetector, BSMDetector, QKDDetector


class TestTwinDetector(unittest.TestCase):

    def setUp(self):
        """Resets the simulation environment for each test."""
        sim_reset()

    @staticmethod
    def setup_twin_detector(name="twin_det", p_dark=0., det_eff=1., visibility=1., num_resolving=True):
        """Setup a TwinDector"""
        twin_det = TwinDetector(name, p_dark=p_dark, det_eff=det_eff, visibility=visibility,
                                num_resolving=num_resolving, num_input_ports=1, num_output_ports=1, meas_operators=[],
                                output_meta={})
        return twin_det

    def test_incorrect_setup(self):
        """Test setup of twin detector with invalid parameter values."""
        with self.assertRaises(ValueError):
            self.setup_twin_detector(p_dark=-1)
        with self.assertRaises(ValueError):
            self.setup_twin_detector(det_eff=-1)
        with self.assertRaises(ValueError):
            self.setup_twin_detector(visibility=-1)

    def test_meas_operators(self):
        """Setup a detector with random valid values for the parameter that affect the measurement operators, and
        check whether the Kraus operators add up to the identity matrix."""
        p_dark, det_eff, visibility = np.random.rand(3, )
        twin_det_non_num_res = self.setup_twin_detector(p_dark=p_dark, det_eff=det_eff, visibility=visibility,
                                                        num_resolving=False)
        twin_det_num_res = self.setup_twin_detector(p_dark=p_dark, det_eff=det_eff, visibility=visibility,
                                                    num_resolving=True)
        for twin_det in [twin_det_non_num_res, twin_det_num_res]:
            # First verify that the measurement operators with a beamsplitter add up to identity
            twin_det._set_meas_operators_with_beamsplitter()
            # Note that the measurement operators are Kraus operators, so that we should take the matrix product
            # of the Hermitian with itself
            matrix_prod_meas_ops = [op.arr.conj().T @ op.arr for op in twin_det._meas_operators]
            self.assertTrue(np.allclose(sum(matrix_prod_meas_ops), np.identity(4, dtype=np.complex_)))
            # Verify the same for the operators without a beamsplitter
            twin_det._set_meas_operators_without_beamsplitter()
            matrix_prod_meas_ops = [op.arr.conj().T @ op.arr for op in twin_det._meas_operators]
            self.assertTrue(np.allclose(sum(matrix_prod_meas_ops), np.identity(4, dtype=np.complex_)))


class TestBSMDetector(unittest.TestCase):

    def setUp(self):
        """Sets up a new simulation environment for each test."""
        sim_reset()

    def _get_output_a(self, message):
        """Callback handler for storing the classical message returned by the detector."""
        self.outputs_a.append((message.items, message.meta["successful_modes"]))

    def _get_output_b(self, message):
        """Callback handler for storing the classical message returned by the detector."""
        self.outputs_b.append((message.items, message.meta["successful_modes"]))

    def setup_detector(self, name, num_resolving=False, p_dark=0., det_eff=1., visibility=1.,
                       allow_multiple_successful_modes=False):
        """Setup a BSMDector, bind its output ports and reset the message storage."""
        bsm_det = BSMDetector(name, num_resolving=num_resolving, p_dark=p_dark, det_eff=det_eff,
                              visibility=visibility, allow_multiple_successful_modes=allow_multiple_successful_modes)
        bsm_det.ports["cout0"].bind_output_handler(self._get_output_a)
        bsm_det.ports["cout1"].bind_output_handler(self._get_output_b)
        self.outputs_a, self.outputs_b = [], []
        return bsm_det

    def test_incorrect_qubit_inputs(self):
        """Test incorrect qubit inputs, where only one arrives or two arrive but are encoded differently."""
        bsm_det = self.setup_detector(name="bsm_det", p_dark=0., det_eff=1., visibility=1., num_resolving=False)
        # Transmit a qubit only from one side
        qubits = qapi.create_qubits(2)
        bsm_det.ports["qin0"].tx_input(qubits[0])
        sim_run()
        bsm_det.ports["qin1"].tx_input(qubits[1])
        sim_run()
        self.assertFalse(self.outputs_a[0][0][0].success)
        self.assertFalse(self.outputs_a[1][0][0].success)
        # Create two qubits and set only one of the two to number state
        qubits = qapi.create_qubits(2)
        qubits[0].is_number_state = True
        bsm_det.ports["qin0"].tx_input(qubits[0])
        bsm_det.ports["qin1"].tx_input(qubits[1])
        with self.assertRaises(QuantumDetectorError):
            sim_run()

    def test_presence_absence_detection_and_inefficiencies(self):
        """Test detections with presence-absence encoding as well as dark counts, detector efficiency and visibility."""
        bsm_det = self.setup_detector(name="bsm_det", p_dark=0., det_eff=1., visibility=1., num_resolving=True)

        def transmit_single_photon(bsm_det=None, both_sides=False):
            """Send a single photon from one or both sides to a detector."""
            qubits = qapi.create_qubits(2)
            for q in qubits:
                q.is_number_state = True
            qapi.operate(qubits[0], ops.X)
            if both_sides:
                qapi.operate(qubits[1], ops.X)
            bsm_det.ports["qin0"].tx_input(qubits[0])
            bsm_det.ports["qin1"].tx_input(qubits[1])
            sim_run()

        # Transmit with perfect settings, measure in presence-absence encoding
        transmit_single_photon(bsm_det)
        bsm_det.p_dark = 1.
        # Transmit with dark counts
        transmit_single_photon(bsm_det)
        bsm_det.p_dark = 0.
        bsm_det.det_eff = 0.
        # Transmit with zero detector efficiency
        transmit_single_photon(bsm_det)
        bsm_det.visibility = 0.
        bsm_det.det_eff = 1.
        # Transmit with full photon distinguishability
        transmit_single_photon(bsm_det, both_sides=True)
        self.assertEqual(self.outputs_a, self.outputs_b)
        self.assertTrue(self.outputs_a[0][0][0].success)
        self.assertIn(self.outputs_a[0][0][0].bell_index, [BellIndex.PSI_MINUS, BellIndex.PSI_PLUS])
        self.assertEqual(self.outputs_a[0][1][0], 0)
        for i in [1, 2, 3]:
            self.assertFalse(self.outputs_a[i][0][0].success)
            self.assertIsNone(self.outputs_a[i][1][0])

    def test_time_bin_detection(self):
        """Test the detection for time-bin encoded qubits."""
        bsm_det = self.setup_detector(name="time_bin_bsm_det")
        # Create two qubits encoded such that there is one photon in each time window
        qubits = qapi.create_qubits(2)
        qapi.operate(qubits[0], ops.X)
        bsm_det.ports["qin0"].tx_input(qubits[0])
        bsm_det.ports["qin1"].tx_input(qubits[1])
        sim_run()
        self.assertEqual(self.outputs_a, self.outputs_b)
        self.assertTrue(self.outputs_a[0][0][0].success)
        self.assertIn(self.outputs_a[0][0][0].bell_index, [BellIndex.PSI_PLUS, BellIndex.PSI_MINUS])
        assert self.outputs_a[0][1] == [0]
        # Create two qubits that have a photon in the same time window
        qubits = qapi.create_qubits(2)
        bsm_det.ports["qin0"].tx_input(qubits[0])
        bsm_det.ports["qin1"].tx_input(qubits[1])
        sim_run()
        self.assertEqual(self.outputs_a, self.outputs_b)
        self.assertFalse(self.outputs_a[1][0][0].success)
        assert self.outputs_a[1][1] == [None]

    def test_multiplexed_detection(self):
        """Test detection of multi-mode presence-absence encoded qubit pairs. Including single and multiple successes
        per round."""
        for allow_multiple_successes in [False, True]:
            # Initialize a set of 100 qubits
            source_modes = 100
            # Fill half the list with None
            qubits_left, qubits_right = [None] * int(source_modes / 2), [None] * int(source_modes / 2)
            # Fill the other half of the list with actual qubits
            for m in range(int(source_modes / 2)):
                q1, q2 = (qapi.create_qubits(2))
                qapi.operate(q1, ops.H)
                qapi.operate([q1, q2], ops.CNOT)
                qapi.operate(q1, ops.Z)
                qapi.operate(q2, ops.X)
                qubits_left.append(q1)
                qubits_right.append(q2)
            detector = self.setup_detector(name="bsm_detector",
                                           allow_multiple_successful_modes=allow_multiple_successes)
            # Transmit the qubits
            detector.ports["qin0"].tx_input(qubits_left)
            detector.ports["qin1"].tx_input(qubits_right)
            sim_run()
            # Check if the right mode was successful
            for output in [self.outputs_a, self.outputs_b]:
                results = output[0][0]
                modes = output[0][1]
                if allow_multiple_successes:
                    assert len(results) == source_modes / 2
                    assert len(modes) == source_modes / 2
                else:
                    assert len(results) == 1
                    assert len(modes) == 1
                for i in range(len(results)):
                    self.assertTrue(results[i].success)
                    self.assertEqual(modes[i], int(source_modes / 2) + i)

    def test_number_resolving_detection(self):
        """Test the number resolving functionality of the detector."""
        # Create 4 qubits in the |1> state
        qubits = qapi.create_qubits(4)
        for q in qubits:
            qapi.operate(q, ops.X)
            q.is_number_state = True
        # Initialize number resolving and non-number resolving detector
        num_res_det = self.setup_detector(name="num_res_det", p_dark=0., det_eff=1., visibility=1., num_resolving=True)
        non_num_res_det = self.setup_detector("non_num_res_det")
        # Send qubits
        non_num_res_det.ports["qin0"].tx_input(qubits[0])
        non_num_res_det.ports["qin1"].tx_input(qubits[1])
        sim_run()
        num_res_det.ports["qin0"].tx_input(qubits[2])
        num_res_det.ports["qin1"].tx_input(qubits[3])
        sim_run()
        # Non-photon-number resolving detector gets two photons but only clicks once due to photon bunching
        self.assertTrue(self.outputs_a[0][0][0].success)
        # Photon-number resolving detector correctly detects two photons, which leads to a failure
        self.assertFalse(self.outputs_a[1][0][0].success)


class TestQKDDetector(unittest.TestCase):

    def setUp(self):
        """Sets up a new simulation environment for each test."""
        sim_reset()

    def _get_measurement_output(self, message):
        """Callback handler for storing the classical message returned by the detector."""
        self.outputs.append(message.items)

    def setup_detector(self, name, num_resolving=False, p_dark=0., det_eff=1., visibility=1.,
                       measurement_basis="Z"):
        """Setup a BSMDector, bind its output ports and reset the message storage."""
        qkd_det = QKDDetector(name, num_resolving=num_resolving, p_dark=p_dark, det_eff=det_eff,
                              visibility=visibility, measurement_basis=measurement_basis)
        qkd_det.ports["cout0"].bind_output_handler(self._get_measurement_output)
        self.outputs = []
        return qkd_det

    def test_incorrect_setup(self):
        """Test setup of detector with invalid parameter values."""
        with self.assertRaises(ValueError):
            self.setup_detector(name="invalid_qkd_det", measurement_basis="W")

    def test_time_bin_measurements(self):
        """Test the regular measurement of time-bin (dual-rail) encoded qubits."""
        qkd_det = self.setup_detector(name="qkd_det_time_bin", num_resolving=True)
        for measurement_basis in ["X", "Y", "Z"]:
            qkd_det.measurement_basis = measurement_basis
            qubits = []
            for _ in range(10):
                qubits.append(qapi.create_qubits(2)[0])
            # First transmit qubit in the |0> (so |01>) state
            qkd_det.ports["qin0"].tx_input(qubits)
            sim_run()
            assert len(self.outputs[0]) == 10
            for output in self.outputs[0]:
                self.assertTrue(output.success)
                self.assertIn(output.outcome, [0, 1])
                self.assertEqual(output.measurement_basis, measurement_basis)
            # Now transmit qubit in the |1> (so |10>) state
            qubit = qapi.create_qubits(2)[0]
            qapi.operate(qubit, ops.X)
            qkd_det.ports["qin0"].tx_input([qubit])
            sim_run()
            assert len(self.outputs[1]) == 1
            for output in self.outputs[1]:
                self.assertTrue(output.success)
                self.assertIn(output.outcome, [0, 1])
            # Finally, transmit a qubit in the None state, i.e. a lost qubit in the |00> state
            qkd_det.ports["qin0"].tx_input([None, None, None])
            sim_run()
            assert len(self.outputs[2]) == 3
            for output in self.outputs[2]:
                self.assertFalse(output.success)
            self.outputs = []

    def test_presence_absence_measurements(self):
        """Test the multiplexed measurement of presence-absence (singe-rail) encoded qubits."""
        qkd_det = self.setup_detector(name="qkd_det_pr_ab_left", num_resolving=True)
        for measurement_basis in ["X", "Y", "Z"]:
            qkd_det.measurement_basis = measurement_basis
            # First transmit qubits in the |01> state
            qubits0 = []
            qubits1 = []
            for i in range(10):
                qubit0, qubit1 = qapi.create_qubits(2)
                qapi.operate(qubit1, ops.X)
                for q in [qubit0, qubit1]:
                    q.is_number_state = True
                qubits0.append(qubit0)
                qubits1.append(qubit1)
            qkd_det.ports["qin0"].tx_input(qubits0)
            qkd_det.ports["qin1"].tx_input(qubits1)
            sim_run()
            assert len(self.outputs[0]) == 10
            for output in self.outputs[0]:
                self.assertTrue(output.success)
                self.assertIn(output.outcome, [0, 1])
                self.assertEqual(output.measurement_basis, measurement_basis)
            # Now transmit qubits in the |10> state
            qubits0 = []
            qubits1 = []
            for i in range(10):
                qubit0, qubit1 = qapi.create_qubits(2)
                qapi.operate(qubit0, ops.X)
                for q in [qubit0, qubit1]:
                    q.is_number_state = True
                qubits0.append(qubit0)
                qubits1.append(qubit1)
            qkd_det.ports["qin0"].tx_input(qubits0)
            qkd_det.ports["qin1"].tx_input(qubits1)
            sim_run()
            assert len(self.outputs[1]) == 10
            for output in self.outputs[1]:
                self.assertTrue(output.success)
                self.assertIn(output.outcome, [0, 1])
            # Next, transmit qubits in the |11> state
            qubits0 = []
            qubits1 = []
            for i in range(10):
                qubit0, qubit1 = qapi.create_qubits(2)
                qapi.operate(qubit0, ops.X)
                qapi.operate(qubit1, ops.X)
                for q in [qubit0, qubit1]:
                    q.is_number_state = True
                qubits0.append(qubit0)
                qubits1.append(qubit1)
            qkd_det.ports["qin0"].tx_input(qubits0)
            qkd_det.ports["qin1"].tx_input(qubits1)
            sim_run()
            assert len(self.outputs[2]) == 10
            for output in self.outputs[2]:
                self.assertFalse(output.success)
            # Finally, transmit qubits in the |00> state
            qubits0 = []
            qubits1 = []
            for i in range(10):
                qubit0, qubit1 = qapi.create_qubits(2)
                for q in [qubit0, qubit1]:
                    q.is_number_state = True
                qubits0.append(qubit0)
                qubits1.append(qubit1)
            qkd_det.ports["qin0"].tx_input(qubits0)
            qkd_det.ports["qin1"].tx_input(qubits1)
            sim_run()
            assert len(self.outputs[3]) == 10
            for output in self.outputs[3]:
                self.assertFalse(output.success)
            self.outputs = []

    def test_correlations(self):
        """Test whether entangled qubits cause the correct correlations in measurements."""
        for encoding in ["presence_absence", "time_bin"]:
            qkd_det_left = self.setup_detector(name="qkd_det_pr_ab_left", num_resolving=True)
            qkd_det_right = self.setup_detector(name="qkd_det_pr_ab_right", num_resolving=True)
            for measurement_basis in ["X", "Y", "Z"]:
                qkd_det_left.measurement_basis = measurement_basis
                qkd_det_right.measurement_basis = measurement_basis
                for bell_state in [b01, b11]:
                    if encoding == "time_bin":
                        qubits = qapi.create_qubits(2)
                        qapi.assign_qstate(qubits, bell_state)
                        qkd_det_left.ports["qin0"].tx_input([qubits[0]])
                        qkd_det_right.ports["qin0"].tx_input([qubits[1]])
                    else:
                        qubits = qapi.create_qubits(4)
                        qapi.assign_qstate(qubits[:2], bell_state)
                        qapi.assign_qstate(qubits[2:], bell_state)
                        for q in qubits:
                            q.is_number_state = True
                        qkd_det_left.ports["qin0"].tx_input([qubits[0]])
                        qkd_det_left.ports["qin1"].tx_input([qubits[2]])
                        qkd_det_right.ports["qin0"].tx_input([qubits[1]])
                        qkd_det_right.ports["qin1"].tx_input([qubits[3]])
                    sim_run()
                    self.assertEqual(self.outputs[0][0].success, self.outputs[1][0].success)
                    if encoding == "time_bin":
                        self.assertTrue(self.outputs[0][0].success)
                    self.assertEqual(self.outputs[0][0].measurement_basis, self.outputs[1][0].measurement_basis)
                    self.assertEqual(self.outputs[0][0].measurement_basis, measurement_basis)
                    # A success only occurs with probability 0.5 for presence-absence encoding
                    if self.outputs[0][0].success:
                        if measurement_basis == "Z":
                            # We expect perfect anti-correlation
                            self.assertNotEqual(self.outputs[0][0].outcome, self.outputs[1][0].outcome)
                        else:
                            if encoding == "time_bin":
                                # We expect perfect (anti-)correlation based on the phase of the Bell state
                                if bell_state is b01:
                                    self.assertEqual(self.outputs[0][0].outcome, self.outputs[1][0].outcome)
                                else:
                                    self.assertNotEqual(self.outputs[0][0].outcome, self.outputs[1][0].outcome)
                            else:
                                # for presensce_absence we expect:
                                # Z: always anti-correlated
                                # X: iff same bell state in both chains: correlations else: anti-correlations
                                # Y: same as X
                                self.assertEqual(self.outputs[0][0].outcome, self.outputs[1][0].outcome)

                    self.outputs = []
                    if encoding == "presence_absence":
                        # test putting different bell states on detectors for presence_absence
                        qubits = qapi.create_qubits(4)
                        qapi.assign_qstate(qubits[:2], b01)
                        qapi.assign_qstate(qubits[2:], b11)
                        for q in qubits:
                            q.is_number_state = True
                        qkd_det_left.ports["qin0"].tx_input([qubits[0]])
                        qkd_det_left.ports["qin1"].tx_input([qubits[2]])
                        qkd_det_right.ports["qin0"].tx_input([qubits[1]])
                        qkd_det_right.ports["qin1"].tx_input([qubits[3]])
                        sim_run()
                        self.assertEqual(self.outputs[0][0].success, self.outputs[1][0].success)
                        self.assertEqual(self.outputs[0][0].measurement_basis, self.outputs[1][0].measurement_basis)
                        self.assertEqual(self.outputs[0][0].measurement_basis, measurement_basis)
                        if self.outputs[0][0].success:
                            # We expect perfect anti-correlation in all basis
                            self.assertNotEqual(self.outputs[0][0].outcome, self.outputs[1][0].outcome)

                        self.outputs = []


if __name__ == "__main__":
    logger.setLevel("WARNING")
    unittest.main()
