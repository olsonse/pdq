import logging
from io import BytesIO

from migen import run_simulation

from host import cli
from testbench.test_spi_pdq2 import TB


logger = logging.getLogger(__name__)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(name)s.%(funcName)s:%(lineno)d] %(message)s")

    buf = BytesIO()
    cli.main(buf)
    tb = TB()

    xfers = []
    cmds = []
    run_simulation(tb, [
        tb.watch_oe(),
        tb.log_xfers(xfers),
        tb.log_cmds(cmds),
        tb.write(buf.getvalue()),
    ], vcd_name="spi_pdq2.vcd")
    # out = np.array(tb.outputs, np.uint16).view(np.int16)
    # plt.plot(out)
    # print(xfers)
