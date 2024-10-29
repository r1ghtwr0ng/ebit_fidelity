import unittest
import netsquid as ns
from netsquid.components.cchannel import ClassicalChannel
from netsquid.components.tests.test_channel import TestChannel
from netsquid_physlayer.classical_errors import LogicalErrorNoiseModel, FixedProbLossModel


class Test_LogicalErrorNoiseModel(unittest.TestCase):

    _test_items = [3, 4.2, "hello", (1, 2, 3)]

    # the expected output when setting the ns.set_random_state(seed=1)
    _expected_output_items = [3, 4.2, "helfo", (0, 2, 3)]

    def test_noise_operation(self):

        # testing with error probability 0 and 1
        for prob_error in [0, 1]:
            clogerrmodel = LogicalErrorNoiseModel(prob_error=prob_error)

            for input_item in self._test_items:
                output_item = [input_item]
                input_list = [input_item]
                clogerrmodel(input_list)
                if prob_error == 0:
                    self.assertEqual(input_list, output_item)
                else:
                    self.assertNotEqual(input_list, output_item)

        # testing with error probability different than 0 or 1
        ns.set_random_state(seed=1)
        clogerrmodel = LogicalErrorNoiseModel(prob_error=0.345)
        for index, input_item in enumerate(self._test_items):
            input_list = [input_item]
            clogerrmodel(input_list)
            self.assertEqual(input_list[0], self._expected_output_items[index])


class Test_LogicalErrorNoiseModel_Channel_integration(TestChannel):

    _test_items = Test_LogicalErrorNoiseModel._test_items

    def test_channel_integration(self):
        # NOTE This should be part of the test of ClassicalChannel
        # in NetSquid
        for prob_error in [0, 1]:
            clogerrmodel = LogicalErrorNoiseModel(prob_error=prob_error)
            cchannel = ClassicalChannel(name="TestChannel",
                                        delay=0,
                                        length=0,
                                        models={"classical_noise_model": clogerrmodel},
                                        classical_code=None)
            for input_item in self._test_items:
                input_item_copy = input_item
                self._wait_for_channel_items()
                self._send_item_on_channel(cchannel, input_item, 0)
                ns.sim_run()
                if prob_error == 0:
                    self.assertEqual(self.read_items, [input_item_copy])
                else:
                    self.assertNotEqual(self.read_items, [input_item_copy])


class Test_FixedProbLossModel(TestChannel):

    _test_items = Test_LogicalErrorNoiseModel._test_items

    # the expected output when setting the ns.set_random_state(seed=303)
    _expected_output_items = [[3], [4.2], [], [(1, 2, 3)]]

    def test_init(self):
        FixedProbLossModel(prob_loss=1.)

    def test_channel_integration(self):
        """
        Test that when we add the FixedProbLossModel to a classical channel,
        then it makes items lost as expected
        """
        ns.set_random_state(seed=303)
        p = 0.234  # some random probability
        for prob_loss in [0, p, 1]:
            lm = FixedProbLossModel(prob_loss=prob_loss)
            cchannel = ClassicalChannel(name="TestChannel",
                                        delay=0,
                                        length=0,
                                        models={"classical_loss_model": lm},
                                        classical_code=None)
            for i in range(len(self._test_items)):
                input_item = self._test_items[i]
                input_item_copy = input_item
                self._wait_for_channel_items()
                self._send_item_on_channel(cchannel, input_item, 0)
                ns.sim_run()
                if prob_loss == 0:
                    self.assertEqual(self.read_items, [input_item_copy])
                elif prob_loss == p:
                    self.assertEqual(self.read_items, self._expected_output_items[i])
                else:
                    # prob_loss == 1
                    self.assertEqual(self.read_items, [])


if __name__ == "__main__":
    unittest.main()
