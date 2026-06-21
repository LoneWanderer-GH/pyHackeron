with Interfaces;
with Interfaces.C;
with Interfaces.C.Extensions;
use Interfaces.C.Extensions;

with Corelec.Types;
use Corelec.Types;



package body Corelec.Decoder is
   use type Corelec.Types.U8;

   function U16 (Msb, Lsb : Corelec.Types.U8) return Corelec.Types.I32 is
   begin
      return Corelec.Types.I32 (Integer (Msb) * 256 + Integer (Lsb));
   end U16;

   procedure Set_Raw
     (Frame : in Corelec.Types.Frame_Type;
      Out_D : in out Corelec.Types.Decoded_Frame) is
   begin
      Out_D.Raw := Frame.Raw;
      Out_D.Frame_Type_Id := Frame.Frame_Type_Id;
      Out_D.Valid := 1;
   end Set_Raw;

   procedure Decode_77
     (Frame : in Corelec.Types.Frame_Type;
      Out_D : in out Corelec.Types.Decoded_Frame) is
      use type Interfaces.C.int;
      use type Interfaces.C.double;
      Ph    : constant Interfaces.C.double := Interfaces.C.double (U16 (Frame.Raw (2), Frame.Raw (3))) / 100.0;
      Redox : constant Corelec.Types.I32 := U16 (Frame.Raw (4), Frame.Raw (5));
      Temp  : constant Interfaces.C.double := Interfaces.C.double (U16 (Frame.Raw (6), Frame.Raw (7))) / 10.0;
      Sel   : constant Interfaces.C.double := Interfaces.C.double (U16 (Frame.Raw (8), Frame.Raw (9))) / 10.0;
   begin
      Out_D.Kind := Corelec.Types.Kind_77;
      if Ph >= 3.5 and then Ph <= 9.5 then
         Out_D.Has_Ph := 1;
         Out_D.Ph := Ph;
      end if;
      if Redox >= 350 and then Redox <= 1000 then
         Out_D.Has_Redox := 1;
         Out_D.Redox := Redox;
      end if;
      if Temp >= 0.0 and then Temp <= 50.0 then
         Out_D.Has_Temp := 1;
         Out_D.Temp := Temp;
      end if;
      if Sel >= 0.0 and then Sel <= 10.0 then
         Out_D.Has_Sel := 1;
         Out_D.Sel := Sel;
      end if;
      Out_D.Alarme := Frame.Raw (10);
      Out_D.Warning := Frame.Raw (11) and 16#0F#;
      --Out_D.Alarm_Rdx := Interfaces.Unsigned_8'Shift_Right (Frame.Raw (11), 4);
      declare
         use type Corelec.Types.U8;
         tmp : Interfaces.Unsigned_8 := 0 ;
      begin
         tmp := Interfaces.Shift_Right (Interfaces.Unsigned_8(Frame.Raw (11)), Natural(4));
         Out_D.Alarm_Rdx := U8(tmp);
      end;

      Out_D.Pompe_Moins_Active := (if (Frame.Raw (12) and 16#40#) /= 0 then 1 else 0);
      Out_D.Regulation_Active := (if (Frame.Raw (12) and 16#20#) /= 0 then 1 else 0);
      Out_D.Pompes_Forcees := (if (Frame.Raw (13) and 16#80#) /= 0 then 1 else 0);
   end Decode_77;

   procedure Decode_83
     (Frame : in Corelec.Types.Frame_Type;
      Out_D : in out Corelec.Types.Decoded_Frame) is
      use type Interfaces.C.double;
   begin
      Out_D.Kind := Corelec.Types.Kind_83;
      Out_D.Has_Ph_Consigne := 1;
      Out_D.Ph_Consigne := Interfaces.C.double (U16 (Frame.Raw (2), Frame.Raw (3))) / 100.0;
      Out_D.Has_Err_Max := 1;
      Out_D.Err_Max := Interfaces.C.double (U16 (Frame.Raw (10), Frame.Raw (11))) / 100.0;
      Out_D.Has_Err_Min := 1;
      Out_D.Err_Min := Interfaces.C.double (U16 (Frame.Raw (12), Frame.Raw (13))) / 100.0;
   end Decode_83;

   procedure Decode_69
     (Frame : in Corelec.Types.Frame_Type;
      Out_D : in out Corelec.Types.Decoded_Frame) is
      use type Interfaces.C.double;
   begin
      Out_D.Kind := Corelec.Types.Kind_69;
      Out_D.Has_Redox_Consigne := 1;
      Out_D.Redox_Consigne := U16 (Frame.Raw (2), Frame.Raw (3));
   end Decode_69;

   procedure Decode_65
     (Frame : in Corelec.Types.Frame_Type;
      Out_D : in out Corelec.Types.Decoded_Frame) is
      use type Interfaces.C.double;
      use type Interfaces.C.int;
      Boost_Remaining_Min : constant Corelec.Types.I32 := Corelec.Types.I32 (Frame.Raw (4));
      Inversion_Period_Min : constant Corelec.Types.I32 := Corelec.Types.I32 (Frame.Raw (6));
   begin
      Out_D.Kind := Corelec.Types.Kind_65;
      Out_D.Boost_Active := (if Boost_Remaining_Min > 0 then 1 else 0);
      Out_D.Has_Boost_Remaining_Min := 1;
      Out_D.Boost_Remaining_Min := Boost_Remaining_Min;
      Out_D.Has_Current_Electrolyse_Percent := 1;
      Out_D.Current_Electrolyse_Percent := Corelec.Types.I32 (Frame.Raw (2));
      Out_D.Has_Inversion_Period_Min := 1;
      Out_D.Inversion_Period_Min := Inversion_Period_Min;
      Out_D.Has_Shutter_Mode_Electrolyse := 1;
      Out_D.Shutter_Mode_Electrolyse_Percent := Corelec.Types.I32 (Frame.Raw (9));
      Out_D.Flow_Switch := (if (Frame.Raw (10) and 16#04#) /= 0 then 1 else 0);
      Out_D.Volet_Actif := (if (Frame.Raw (10) and 16#10#) /= 0 then 1 else 0);
      Out_D.Volet_Force := (if (Frame.Raw (10) and 16#08#) /= 0 then 1 else 0);
      Out_D.Has_Inversion_Timer_Min := 1;
      Out_D.Inversion_Timer_Min := Corelec.Types.I32 (Frame.Raw (8));
   end Decode_65;

   procedure Decode_Frame
     (Frame : in Corelec.Types.Frame_Type;
      Out_D : out Corelec.Types.Decoded_Frame) is
   begin
      Out_D := (others => <>);
      Set_Raw (Frame, Out_D);

      case Integer (Frame.Frame_Type_Id) is
         when 77 => Decode_77 (Frame, Out_D);
         when 83 => Decode_83 (Frame, Out_D);
         when 69 => Decode_69 (Frame, Out_D);
         when 65 => Decode_65 (Frame, Out_D);
         when others =>
            Out_D.Kind := Corelec.Types.Kind_Unknown;
      end case;
   end Decode_Frame;
end Corelec.Decoder;
