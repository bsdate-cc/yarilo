from yarilo.ddc import vcp_codes


def test_vcp_codes_from_capabilities_string():
    caps = "(prot(monitor)type(LCD)model(MAG275CQ)cmds(01 02 03 07 0C E3 F3)vcp(02 04 05 08 10 12 14(05 08 0B) 16 18 1A 60(0F 11 12) D6(01 05) DC)mswhql(1)mccs_ver(2.2))"
    assert vcp_codes(caps) == [0x02, 0x04, 0x05, 0x08, 0x10, 0x12, 0x14, 0x16, 0x18, 0x1A, 0x60, 0xD6, 0xDC]


def test_vcp_codes_missing():
    assert vcp_codes("") == []
    assert vcp_codes(None) == []
