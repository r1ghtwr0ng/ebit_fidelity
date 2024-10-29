import netsquid as ns
from netsquid_physlayer.heralded_connection import MiddleHeraldedConnection


def test_heralded_connection():

    length = 10
    speed_of_light = 100
    heralded_connection = MiddleHeraldedConnection(name="test_heralded_connection", length=length, p_loss_init=0,
                                                   p_loss_length=0, speed_of_light=speed_of_light)
    # check if properties are correct
    cch_A_length = heralded_connection.subcomponents["CCh_A"].properties["length"]
    cch_B_length = heralded_connection.subcomponents["CCh_B"].properties["length"]
    assert cch_A_length == heralded_connection.subcomponents["QCh_A"].properties["length"]
    assert cch_A_length == length / 2
    assert cch_B_length == heralded_connection.subcomponents["QCh_B"].properties["length"]
    assert cch_B_length == length / 2

    print(heralded_connection.subcomponents["QCh_B"].models['delay_model'].properties)

    # check if correct response
    for port in heralded_connection.ports.values():
        qubit = ns.qubits.qubitapi.create_qubits(1)
        ns.qubits.operate(qubit, ns.qubits.operators.H)
        port.tx_input(qubit)
    expected_duration = length / speed_of_light * 1E9
    ns.sim_run(duration=expected_duration + 1e-5)
    for port in heralded_connection.ports.values():
        assert port.rx_output() is not None


if __name__ == "__main__":
    test_heralded_connection()
