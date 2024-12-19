import gc
import tracemalloc
import netsquid as ns

from netsquid.components.qprocessor import QuantumProcessor
from qpu_programs import EmitProgram


class MemTest(ns.pydynaa.Entity):
    def __init__(self, name):
        super().__init__()
        self.name = name
        self.processor = self.__create_processor(name, 2)

    def __create_processor(self, name, qbit_count):
        physical_instructions = [
            # TODO investigate clearing up this
            ns.components.qprocessor.PhysicalInstruction(
                ns.components.instructions.INSTR_INIT, duration=3, parallel=True
            ),
            # TODO investigate clearing up this
            ns.components.qprocessor.PhysicalInstruction(
                ns.components.instructions.INSTR_EMIT, duration=1, parallel=True
            ),
        ]
        # TODO fix mem leak in QPU module
        processor = QuantumProcessor(
            name,
            num_positions=qbit_count,
            phys_instructions=physical_instructions,
        )
        return processor

    def program_done_callback(self, *args, **kwargs):
        used_positions = self.processor.used_positions
        if used_positions:
            self.processor.discard(used_positions)
        self.processor.reset()

    def emit(self, position=0):
        self.processor.set_program_done_callback(self.program_done_callback)
        prog = EmitProgram(position, 1)
        self.processor.execute_program(prog)
        prog.reset()
        del prog


def main():
    attempts = 50000
    tracemalloc.start()  # Start tracing memory allocations

    for i in range(attempts):
        # The print is another cause of mem usage but its small
        print(f"{i}/{attempts}", end="\r")

        ns.sim_reset()

        alice = MemTest("AliceQPU")
        alice.emit()

        ns.sim_run()

        alice.processor.reset
        alice.processor.remove
        del alice.processor
        del alice

        # Take a memory snapshot every 1000 iterations
        if (1 + i) % 50000 == 0:
            gc.collect()
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics("lineno")

            print(f"\n[Iteration {i}] Top Memory Usage:")
            for stat in top_stats:
                print(stat)

    tracemalloc.stop()


if __name__ == "__main__":
    main()
