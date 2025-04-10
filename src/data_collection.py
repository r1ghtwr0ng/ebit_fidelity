import netsquid as ns
from utils import get_fidelities
from netsquid.protocols import Signals


# DataCollection handler
def collect_fidelity_data(evexpr):
    first_protocol = evexpr.first_term.triggered_events[-1].source
    second_protocol = evexpr.second_term.triggered_events[-1].source
    first_result = first_protocol.get_signal_result(Signals.FINISHED)
    second_result = second_protocol.get_signal_result(Signals.FINISHED)

    # Get the respective QPUs
    alice = first_protocol.node
    bob = second_protocol.node

    # Get results
    fidelity = get_fidelities(alice, bob)
    success = first_result["success"] and second_result["success"]
    log = first_result["log"]
    simtime = ns.sim_time()

    results = {
        "fidelity": fidelity,
        "simtime": simtime,
        "attempt_log": log,
        "success": success,
    }
    return results
