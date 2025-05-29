import re
from pynmea2 import NMEASentence
from pynmea2 import TalkerSentence
# from geographiclib.geodesic import Geodesics
from decimal import Decimal


class EPR(TalkerSentence):
    fields = (
        ("engine_no", "engine_no"),
        ("pressure", "pressure"),
        ("angle", "angle"),
        ("A", "A"),
    )


class OUT(TalkerSentence):
    fields = (
        ("att", "att"),
        ("roll", "roll"),
        ("pitch", "pitch"),
        ("yaw", "yaw"),
    )


class EPD(TalkerSentence):
    fields = (
        ("engine_no", "engine_no"),
        ("oil_press", "oil_press"),
        ("oil_temp", "oil_temp"),
        ("engine_temp", "engine_temp"),
        ("alternator_potentia", "alternator_potentia"),
        ("fuel_rate", "fuel_rate"),
        ("total_engine_hours", "total_engine_hours"),
        ("coolant_pressure", "coolant_pressure"),
        ("fuel_pressure", "fuel_pressure"),
        ("discrete_status_1", "discrete_status_1"),
        ("discrete_status_2", "discrete_status_2"),
        ("percent_engine_load", "percent_engine_load"),
        ("percent_engine_torque", "percent_engine_torque"),
    )


class DTM(TalkerSentence):
    fields = (
        ("datum", "datum"),
        ("subd_datum", "subd_datum"),
        ("lat", "lat"),
        ("lat_dir", "lat_dir"),
        ("lon", "lon"),
        ("lon_dir", "lon_dir"),
        ("altitude", "altitude"),
        ("datum_code", "datum_code"),
    )


class HTD(TalkerSentence):
    fields = (
        ("Override", "Override"),
        ("Commanded rudder angle", "CRA"),
        ("Commanded rudder direction", "CRD"),
        ("Selected steering mode", "SSM"),
        ("Turn mode", "TM"),
        ("Commanded rudder limit", "CRL"),
        ("Commanded off-heading limit", "COL"),
        ("Commanded radius of turn for heading changes", "CROT"),
        ("Commanded rate of turn for heading changes", "CRAOT"),
        ("Commanded heading-to-steer", "CH"),
        ("Commanded off-track limit", "COTL"),
        ("Commanded track", "CT"),
        ("Heading Reference in use", "HRIU"),
        ("Rudder status ", "RS"),
        ("Off-heading status", "OHS"),
        ("Off-track status", "OTS"),
    )

class IND(TalkerSentence):
    fields = (
        ("NEUTRAL_LED", "NEUTRAL_LED"),
        ("ACTIVE_LED", "ACTIVE_LED"),
        ("SYNC_LED", "SYNC_LED"),
    )

class VER(TalkerSentence):
    fields = (
        ("LPS_L_vol", "LPS_L_vol"),
        ("LPS_R_vol", "LPS_R_vol"),
    )   
class RAP(TalkerSentence):
    fields = (
        ("EngineInstance", "EngineInstance"),
        ("EngineSpeed", "EngineSpeed"),
        ("EngineBoostPressure", "EngineBoostPressure"),
        ("EngineTiltTrim", "EngineTiltTrim"),
    )   
class PAR(TalkerSentence):
    fields = (
        ("EngineInstance", "EngineInstance"),
        ("TransmissionGear", "TransmissionGear"),
        ("OilPressure", "OilPressure"),
        ("OilTemperature", "OilTemperature"),
        ("DiscreteStatus1", "DiscreteStatus1"),
    ) 
class DER(TalkerSentence):
    fields = (
        ("RudderOrder", "RudderOrder"),
    )   
class ACK(TalkerSentence):
    fields = (
        ("RudderFeedback", "RudderFeedback"),
    )   
class ODE(TalkerSentence):
    fields = (
        ("Pilot_Mode", "Pilot_Mode"),
    ) 
class ING(TalkerSentence):
    fields = (
        ("Heading", "Heading"),
    ) 
class RSE(TalkerSentence):
    fields = (
        ("Course", "Course"),
    ) 



class customSentence(NMEASentence):
    sentence_re = re.compile(
        r"""
        # start of string, optional whitespace, optional '$'
        ^\s*\$?

        # message (from '$' or start to checksum or end, non-inclusve)
        (?P<nmea_str>
            # sentence type identifier
            (?P<sentence_type>
                    
                # (P\w{3})|

                             
                # query sentence, ie: 'CCGPQ,GGA'
                # NOTE: this should have no data
                (\w{2}\w{2}Q,\w{3})|

                # taker sentence, ie: only catch last three word
                (\w{0,}\w{3},)
                             
                     
            )
            # rest of message
            (?P<data>[^*]*)
        )
        # checksum: *HH
        (?:[*](?P<checksum>[A-F0-9]{2}))?

        # optional trailing whitespace
        \s*[\r\n]*$
        """,
        re.X | re.IGNORECASE,
    )

    talker_re = re.compile(r"^(?P<talker>.*?)(?P<sentence>\w{3}),$")



    # query_re = \
    #     re.compile(r'^(?P<talker>\w{2})(?P<listener>\w{2})Q,(?P<sentence>\w{3})$')

    # proprietary_re = \
    #     re.compile(r'^P(?P<manufacturer>\w{3})$')

    @staticmethod
    def parse(line, check=False):
        match = customSentence.sentence_re.match(line)  # match.groupdict()
        nmea_str = match.group("nmea_str")
        data_str = match.group("data")
        checksum = match.group("checksum")
        sentence_type = match.group("sentence_type").upper()
        data = data_str.split(",")

        # 判斷校驗值
        if checksum:
        # if check:
            cs1 = int(checksum, 16)
            cs2 = NMEASentence.checksum(nmea_str)
            if cs1 != cs2:
                raise ValueError(
                    "checksum does not match: %02X != %02X" % (cs1, cs2), data
                )
        elif check:
            raise ValueError("strict checking requested but checksum missing", data)

        talker_match = customSentence.talker_re.match(sentence_type)
        
        if talker_match:
            talker = talker_match.group("talker")  # PMAR
            sentence = talker_match.group("sentence")  # EPR
            cls = TalkerSentence.sentence_types.get(sentence)
            if not cls:
                # TODO instantiate base type instead of fail
                raise ValueError("Unknown sentence type %s" % sentence_type, line)
            return cls(talker, sentence, data)

    def parse_nmea_type(line, check=True):
        try:
            match = customSentence.sentence_re.match(line)  # match.groupdict()
            sentence_type = match.group("sentence_type").upper()
            talker_match = customSentence.talker_re.match(sentence_type)
            if talker_match:
                # talker = talker_match.group("talker")  # PMAR
                sentence = talker_match.group("sentence")  # EPR
                change_name = {"EPR": "PMAREPR",
                               "OUT": "PMAROUT", 
                               "EPD": "PMAREPD",}
                if sentence in change_name:
                    return change_name[sentence]
                return sentence
        except:
            pass

class customNemaJson(customSentence):
    def __init__(self):
        pass

    
    def formatjson(self,nmea_sentence):
        data = nmea_sentence
        # print(data)
        try:
            parse = customNemaJson.parse(data)
            selectedDict = {}
            for prop_name in parse.name_to_idx:
                value = getattr(parse, prop_name)
                if type(value)== type(Decimal("10")):
                    selectedDict[prop_name] = float(str(value))
                else:
                    selectedDict[prop_name] = str(value)

            #轉經緯度
            # if "lat" in selectedDict:
            #     try:  # IIDTM lat沒有此屬性
            #         selectedDict["lat"] = parse.latitude
            #         selectedDict["lon"] = parse.longitude
            #     except:
            #         pass
            return selectedDict
        except:
            print(f"[警告] Nema沒有此格式，請檢查後執行 {data}")
            # return {"worng":1}



        #轉經緯度
        # if "lat" in selectedDict:
        #     try:  # IIDTM lat沒有此屬性
        #         selectedDict["lat"] = parse.latitude
        #         selectedDict["lon"] = parse.longitude
        #     except:
        #         pass
        # return selectedDict

    
        


if __name__ == "__main__":
    # 記得只讀取array[3]
    # nmea_sentence = ["79350583","1691038881.72411270","PMAREPR","$PMAREPR,1,0,,A*09"]

    # 測試用
    # nmea_sentence = "$IIROT,-10,A*24"
    # nmea_sentence = "$PMAREPR,1,0,,A*09"
    # nmea_sentence = "$GPGGA,184353.07,1929.045,S,02410.506,E,1,04,2.6,100.00,M,-33.9,M,,0000*6D"
    # nmea_sentence = "$PMAREPD,0,0,37.7,36,26.85,0,682.15,,,0,0,0,0,A*07"
    # nmea_sentence = "$IIXDR,V,,M,FUEL#4,V,,M,FUEL#4*58"
    # nmea_sentence = "$PMAROUT,ATT,-3.2,0.8,-94.0,,,,,*37"
    # nmea_sentence = "$IIHTD,V,,,M,N,,,,,,,,,A,,,*60"
    # nmea_sentence = "$IIHSC,,T,,M*41"
    # nmea_sentence ="$IIVLW,0,N,0,N,,N,,N*4D"
    # nmea_sentence ="$IIDTM,W84,,0,N,0,E,0,W84*66" #自刻
    # nmea_sentence = "$PMAROUT,ATT,-3.2,0.8,-94.0,,,,,*55" #錯誤校驗碼
    # nmea_sentence ="$IIRSA,0.30,A,,V*4A"
    # nmea_sentence = "$PMAREPD,0,0,37.7,36,26.85,0,,,,0,0,0,0,A*11"
    # nmea_sentence ="$PMAREPD,1,40,38.2,36,27,0,,,,0,0,0,0,A*0C"
    # nmea_sentence ="$IIGLL,2236.37411,N,12017.79149,E,,V,N*4A"
    # nmea_sentence ="$IIHDG,266.1,,,,*4A"
    # nmea_sentence ="$IIRPM,E,1,0,,A*66"
    # nmea_sentence ="$IIRPM,E,0,0,,A*67"
    # nmea_sentence='$IIZDA,085240.8992,26,09,2023,,*7E'
    # nmea_sentence="$IIGLL,2236.27814,N,12018.11199,E,024306.6,A,A*4D"
    # nmea_sentence="$IND,0,1,3" #注意如果只有3個字元都會被歸類在此
    # nmea_sentence="$Lever,0,1"
    nmea_sentence="$EngRap,0,1,2,3"
    # nmea_sentence="$TransPar,0,1,2,3,4"
    # nmea_sentence="$RudderOrde,0"
    # nmea_sentence="$RudderFeedback,0"
    # nmea_sentence="$Pilot_Mode,0"
    # nmea_sentence="$Heading,0" #磁方向
    # nmea_sentence="$HeadingToSteerCourse,0" #航向(真方向)
    nmea_sentence="$RudderOrder,-20"
    result = customNemaJson().formatjson(nmea_sentence)
    print(result)
    # print(customSentence.parse_nmea_type(nmea_sentence))
    # customSentence.formatsocket(nmea_sentence)
    # print(customSentence.windy())


