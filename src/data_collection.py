import logging
import netsquid as ns
from utils import get_fidelities
from netsquid.protocols import Signals


# DataCollection handler
def collect_fidelity_data(evexpr):
    """
    Extract data from an EventExpression object and create a dictionary
    containing the necessary metrics (fidelity, simulation time, status)

    Parameters
    ----------
    evexpr : pydynaa.core.EventExpression
        Event containing information about the protocol runs.

    Returns
    -------
    dict
        Return the metrics via a dict object.

    Examples
    --------
    >>> subprotocols_done = self.await_signal(
    >>>     self.subprotocol_qnode_1, signal_label=Signals.FINISHED
    >>> )
    >>> yield subprotocols_done
    >>> data_point = collect_fidelity_data(subprotocols_done)
    """
    # Get logger
    logger = logging.getLogger("data_logger")

    first_protocol = evexpr.first_term.triggered_events[-1].source
    second_protocol = evexpr.second_term.triggered_events[-1].source
    first_result = first_protocol.get_signal_result(Signals.FINISHED)
    second_result = second_protocol.get_signal_result(Signals.FINISHED)

    # Get the respective QPUs
    alice = first_protocol.node
    bob = second_protocol.node

    # Get results
    fidelity = get_fidelities(alice, bob)[0]
    success = first_result["success"] and second_result["success"]
    log = first_result["log"]
    simtime = ns.sim_time()

    results = {
        "fidelity": fidelity,
        "simtime": simtime,
        "attempt_log": log,
        "success": success,
    }
    logger.info(f"Data returned by data collection handler: {results}")
    return results
