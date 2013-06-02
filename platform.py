from mibuild.generic_platform import *
from mibuild.xilinx_ise import XilinxISEPlatform, CRG_SE

_io = [
        ("comm", 0,
            Subsignal("data", Pins(*
                "P101 P91 P76 P72 P71 P60 P58 P57".split())),
            Subsignal("rdl", Pins("P97")),
            Subsignal("rxfl", Pins("P54")),
            # NET "clk_comm1" TNM_NET = clk_comm1;
            ),

        ("addr", 0, Pins("P32 P6 P14 P43")),

        ("writing", 0, Pins("P159")),
        ("wave", 0, Pins("P110")),
        ("write", 0, Pins("P102")),

        ("aux", 0, Pins("P99")),
        ("branch", 0, Pins("P118 P124 P98")),

        ("clk_dac", 0, Pins("P80")),
        #    Misc("TMN_NET = clk_dac")),
        ("dac_reset", 0, Pins("P96")),

        ("dac", 0,
            Subsignal("clk_p", Pins("P89")),
            Subsignal("clk_n", Pins("P90")),
            Subsignal("data_p", Pins(*(
                "P106 P108 P112 P115 P119 P122 P126 P128 "
                "P132 P134 P137 P139 P144 P146 P150 P152").split())),
            Subsignal("data_n", Pins(*(
                "P107 P109 P113 P116 P120 P123 P127 P129 "
                "P133 P135 P138 P140 P145 P147 P151 P153").split())),
            Subsignal("data_clk_p", Pins("P93")),
            Subsignal("data_clk_n", Pins("P94")),
            IOStandard("LVDS_25"),
            ),

        ("dac", 1,
            Subsignal("clk_p", Pins("P68")),
            Subsignal("clk_n", Pins("P69")),
            Subsignal("data_p", Pins(*(
                "P160 P162 P164 P167 P171 P82 P177 P180 "
                "P74 P185 P189 P192 P196 P199 P202 P205").split())),
            Subsignal("data_n", Pins(*(
                "P161 P163 P165 P168 P172 P83 P178 P181 "
                "P75 P186 P190 P193 P197 P200 P203 P206").split())),
            Subsignal("data_clk_p", Pins("P77")),
            Subsignal("data_clk_n", Pins("P78")),

            IOStandard("LVDS_25"),
            ),

        ("dac", 2,
            Subsignal("clk_p", Pins("P62")),
            Subsignal("clk_n", Pins("P63")),
            Subsignal("data_p", Pins(*(
                "P2 P4 P8 P11 P15 P18 P22 P24 "
                "P28 P30 P33 P35 P39 P41 P47 P49").split())),
            Subsignal("data_n", Pins(*(
                "P3 P5 P9 P12 P16 P19 P23 P25 "
                "P29 P31 P34 P36 P40 P42 P48 P50").split())),
            Subsignal("data_clk_p", Pins("P64")),
            Subsignal("data_clk_n", Pins("P65")),
            IOStandard("LVDS_25"),
            ),
        #TIMEGRP "dac_Out" OFFSET = OUT 10 ns AFTER "clk_dac";
        ]

class Platform(XilinxISEPlatform):
    def __init__(self):
        XilinxISEPlatform.__init__(self, "xc3s500e-4fg320-2", _io,
                lambda p: CRG_SE(p, "clk_dac", "dac_reset", 20.0))