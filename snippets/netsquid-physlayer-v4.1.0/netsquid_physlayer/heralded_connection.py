import netsquid as ns
from netsquid_physlayer.detectors import BSMDetector


__all__ = [
    'HeraldedConnection',
    'MiddleHeraldedConnection',
    'SameChannelsHeraldedConnection'
]


class HeraldedConnection(ns.nodes.Connection):
    """Heralded connection consisting of fibers and a midpoint station containing a Bell-state measurement detector.

    HeraldedConnection is subclassed from :class:`~netsquid.nodes.Connection` and therefore has two ports: "A" and "B".
    Internally, the HeraldedConnection consists of
    - two quantum channels (QC), forwarding messages put on the ports "A" and "B" of HeraldedConnection to the midpoint,
    - a midpoint station (MS), which consists of a Bell-state detector :class:`~.bsm_detector.BSMDetector`,
    - two classical channels (CC), forwarding messages from the midpoint station to the ports "A" and "B".

    .. code-block :: text

            ----------------------------
            | > CC <> -------- <> CC < |
        A > |         |  MS  |         | < B
            | > QC <> -------- <> QC < |
            ----------------------------

    HeraldedConnection can be used to simulate heralded entanglement generation, where two nodes send entangled photons
    to a midpoint station where a Bell-state measurement using linear optics is performed.
    For more information about heralded entanglement generation, see e.g. the paper `"Inside Quantum Repeaters"
    by Munro et al. <https://ieeexplore.ieee.org/document/7010905>`_.

    Parameters
    ----------
    name: str
        name of the component
    length_A: float
        length [km] of fiber on "A" side of heralded connection
    length_B: float
        length [km] of fiber on "B" side of heralded connection
    p_loss_init_A: float (optional)
        probability that photons are lost when entering connection on "A" side
    p_loss_length_A: float (optional)
        attenuation coefficient [dB/km] of fiber between "A" and midpoint
    speed_of_light_A: float (optional)
        speed of light [km/s] in fiber on "A" side of heralded connection
    p_loss_init_B: float (optional)
        probability that photons are lost when entering connection on "B" side
    p_loss_length_B: float (optional)
        attenuation coefficient [dB/km] of fiber between "B" and midpoint
    speed_of_light_B: float (optional)
        speed of light [km/s] in fiber on "B" side of heralded connection
    dark_count_probability: float (optional)
        dark-count probability per detection
    detector_efficiency: float (optional)
        probability that the presence of a photon leads to a detection event
    visibility: float (optional)
        Hong-Ou-Mandel visibility of photons that are being interfered (measure of photon indistinguishability)
    num_resolving : bool (optional)
        determines whether photon-number-resolving detectors are used for the Bell-state measurement

    Notes
    -----
    Uses :class:`~.bsm_detector.BSMDetector` as midpoint station. For details about how qubits are processed and
    what kind of response messages are sent, see the documentation of that class.
    The classical and quantum connections of the same side of the HeraldedConnection represent the same physical
    fiber and therefore always have the same properties and length.
    Quantum channels are :class:`~netsquid.components.qchannel.QuantumChannel` and loss of messages is modelled using
    :class:`~netsquid.components.models.FibreLossModel`.
    Classical channels are :class:`~netsquid.components.cchannel.ClassicalChannel`.
    Both types of channels delay messages using :class:`~netsquid.components.models.FibreDelayModel`.

    """
    def __init__(self, name, length_A, length_B, p_loss_init_A=0, p_loss_length_A=0.25, speed_of_light_A=200000,
                 p_loss_init_B=0, p_loss_length_B=0.25, speed_of_light_B=200000, dark_count_probability=0,
                 detector_efficiency=1., visibility=1., num_resolving=False):

        super().__init__(name=name)

        # create models
        delay_model_A = ns.components.models.FibreDelayModel(c=speed_of_light_A)
        delay_model_B = ns.components.models.FibreDelayModel(c=speed_of_light_B)
        loss_model_A = ns.components.models.FibreLossModel(p_loss_init=p_loss_init_A, p_loss_length=p_loss_length_A)
        loss_model_B = ns.components.models.FibreLossModel(p_loss_init=p_loss_init_B, p_loss_length=p_loss_length_B)

        # create classical channels
        cchannel_A = ns.components.cchannel.ClassicalChannel(name="CChannel_A_of_{}".format(self.name),
                                                             length=length_A,
                                                             models={"delay_model": delay_model_A})
        cchannel_B = ns.components.cchannel.ClassicalChannel(name="CChannel_B_of_{}".format(self.name),
                                                             length=length_B,
                                                             models={"delay_model": delay_model_B})

        # create quantum channels
        qchannel_A = ns.components.qchannel.QuantumChannel("QChannel_A_of_{}".format(self.name), length=length_A,
                                                           models={"delay_model": delay_model_A,
                                                                   "quantum_loss_model": loss_model_A},
                                                           transmit_empty_items=True)
        qchannel_B = ns.components.qchannel.QuantumChannel("QChannel_B_of{}".format(self.name), length=length_B,
                                                           models={"delay_model": delay_model_B,
                                                                   "quantum_loss_model": loss_model_B},
                                                           transmit_empty_items=True)

        # create detector
        bsmdetector = BSMDetector(name="BSMDetector_of_{}".format(self.name), p_dark=dark_count_probability,
                                  det_eff=detector_efficiency, visibility=visibility, num_resolving=num_resolving)

        # add as subcomponents
        self.add_subcomponent(cchannel_A, "CCh_A")
        self.add_subcomponent(cchannel_B, "CCh_B")
        self.add_subcomponent(qchannel_A, "QCh_A")
        self.add_subcomponent(qchannel_B, "QCh_B")
        self.add_subcomponent(bsmdetector, "BSMDet")

        # connect ports
        qchannel_A.ports["recv"].connect(bsmdetector.ports["qin0"])
        qchannel_B.ports["recv"].connect(bsmdetector.ports["qin1"])
        cchannel_A.ports["send"].connect(bsmdetector.ports["cout0"])
        cchannel_B.ports["send"].connect(bsmdetector.ports["cout1"])
        self.ports["A"].forward_input(qchannel_A.ports["send"])
        self.ports["B"].forward_input(qchannel_B.ports["send"])
        cchannel_A.ports["recv"].forward_output(self.ports["A"])
        cchannel_B.ports["recv"].forward_output(self.ports["B"])


class SameChannelsHeraldedConnection(HeraldedConnection):
    """Heralded connection for which the fibers on both sides have the same properties, but can have different lengths.

    SameChannelsHeraldedConnection is derived from :class:`~.heralded_connection.HeraldedConnection`.

    Parameters
    ----------
    name: str
        name of the component
    length_A: float
        length [km] of fiber on "A" side of heralded connection.
    length_B: float
        length [km] of fiber on "B" side of heralded connection.
    p_loss_init: float (optional)
        probability that photons are lost when entering connection the connection on either side.
    speed_of_light: float (optional)
        speed of light [km/s] in fiber on either side.
    p_loss_length: float (optional)
        attenuation coefficient [dB/km] of fiber on either side.
    dark_count_probability: float (optional)
        dark-count probability per detection
    detector_efficiency: float (optional)
        probability that the presence of a photon leads to a detection event
    visibility: float (optional)
        Hong-Ou-Mandel visibility of photons that are being interfered (measure of photon indistinguishability)
    num_resolving : bool (optional)
        determines whether photon-number-resolving detectors are used for the Bell-state measurement

    """
    def __init__(self, name, length_A, length_B, p_loss_init=0, p_loss_length=0.25, speed_of_light=200000,
                 dark_count_probability=0, detector_efficiency=1., visibility=1., num_resolving=False):

        super().__init__(name=name, length_A=length_A, length_B=length_B, p_loss_init_A=p_loss_init,
                         p_loss_init_B=p_loss_init, p_loss_length_A=p_loss_length, p_loss_length_B=p_loss_length,
                         speed_of_light_A=speed_of_light, speed_of_light_B=speed_of_light,
                         dark_count_probability=dark_count_probability, detector_efficiency=detector_efficiency,
                         visibility=visibility, num_resolving=num_resolving)


class MiddleHeraldedConnection(SameChannelsHeraldedConnection):
    """Heralded connection for which the fibers on both sides have the same properties and the same lengths.

    MiddleHeraldedConnection derived from :class:`~.heralded_connection.SameChannelsHeraldedConnection`.

    Parameters
    ----------
    name: str
        name of the component
    length: float
        total length [km] of heralded connection (i.e. sum of fibers on both sides on midpoint station).
    p_loss_init: float (optional)
        probability that photons are lost when entering connection the connection on either side.
    speed_of_light: float (optional)
        speed of light [km/s] in fiber on either side.
    p_loss_length: float (optional)
        attenuation coefficient [dB/km] of fiber on either side.
    dark_count_probability: float (optional)
        dark-count probability per detection
    detector_efficiency: float (optional)
        probability that the presence of a photon leads to a detection event
    visibility: float (optional)
        Hong-Ou-Mandel visibility of photons that are being interfered (measure of photon indistinguishability)
    num_resolving : bool (optional)
        determines whether photon-number-resolving detectors are used for the Bell-state measurement
    """
    def __init__(self, name, length, p_loss_init=0, p_loss_length=0.25, speed_of_light=200000,
                 dark_count_probability=0, detector_efficiency=1., visibility=1., num_resolving=False):

        super().__init__(name=name, length_A=length / 2, length_B=length / 2, p_loss_init=p_loss_init,
                         p_loss_length=p_loss_length, speed_of_light=speed_of_light,
                         dark_count_probability=dark_count_probability, detector_efficiency=detector_efficiency,
                         visibility=visibility, num_resolving=num_resolving)