from migen import *
from migen.fhdl.specials import _MemoryPort


class SplitMem(Module):
    def __init__(self, width, depth, init=None, name=None):
        self.width = width
        self.depth = depth
        if init is not None:
            init = list(init)
        self.widths = [i for i in range(log2_int(depth, need_pow2=False))
                                        if (depth >> i) & 1]
        self.widths.reverse()
        self.mems = []
        for m, w in enumerate(self.widths):
            d = 1 << w
            i = None
            if init is not None:
                i = init[:d]
                del init[:d]
            n = None
            if name is not None:
                n = name + "{}".format(m)
            self.mems.append(Memory(width, depth=d, init=i, name=n))
        self.specials += self.mems

    def get_port(self, write_capable=False, async_read=False,
                 has_re=False, we_granularity=0, mode=WRITE_FIRST,
                 clock_domain="sys"):
        ports = [mem.get_port(write_capable=write_capable,
                              async_read=async_read, has_re=has_re,
                              we_granularity=we_granularity, mode=mode,
                              clock_domain=clock_domain) for mem in self.mems]
        self.specials += ports

        adr = Signal(max=self.depth)
        self.comb += [p.adr.eq(adr) for p in ports]
        sel = Signal(max=len(ports))
        self.comb += [
            If(~adr[w], sel.eq(i))
        for i, w in enumerate(self.widths)]
        dat_r = Signal(self.width)
        self.comb += dat_r.eq(Array([p.dat_r for p in ports])[sel])
        if we_granularity >= self.width:
            we_granularity = 0
        if write_capable:
            if we_granularity:
                we = Signal(self.width//we_granularity)
            else:
                we = Signal()
            self.comb += Array([p.we for p in ports])[sel].eq(we)
            dat_w = Signal(self.width)
            self.comb += [p.dat_w.eq(dat_w) for p in ports]
        else:
            we = None
            dat_w = None
        if has_re:
            re = Signal()
            self.comb += [p.re.eq(re) for p in ports]
        else:
            re = None
        mp = _MemoryPort(adr, dat_r, we, dat_w,
                         async_read, re, we_granularity, mode,
                         clock_domain)
        self.specials += mp  # will not emit verilog
        return mp


if __name__ == "__main__":
    from migen.fhdl.verilog import convert

    @SplitMemory()
    class TB(Module):
        def __init__(self):
            #self.submodules.smem = SplitMem(16, 20)
            self.specials.smem = Memory(16, 22)

            #self.specials += self.smem.get_port()
            self.specials += self.smem.get_port(write_capable=True)
            #self.specials += self.smem.get_port(write_capable=True,
            #                                    we_granularity=8)
            #self.specials += self.smem.get_port(has_re=True)

    print(convert(TB()))
