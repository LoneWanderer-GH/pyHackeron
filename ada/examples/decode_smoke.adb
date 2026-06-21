with Ada.Text_IO; use Ada.Text_IO;
with Corelec.Decoder;
with Corelec.Protocol;
with Corelec.Types;

procedure Decode_Smoke is
   Raw   : Corelec.Types.Frame_Array := (0 => 42, 1 => 77, 2 => 2, 3 => 196, 4 => 2, 5 => 88, 6 => 0, 7 => 215, 8 => 0, 9 => 40, 10 => 1, 11 => 16#21#, 12 => 16#60#, 13 => 16#80#, 14 => 0, 15 => 0, 16 => 42);
   Frame : Corelec.Types.Frame_Type;
   Dec   : Corelec.Types.Decoded_Frame;
begin
   Raw (15) := Corelec.Protocol.CRC (Raw, 15);
   if Corelec.Protocol.Parse_Frame (Raw, Frame) then
      Corelec.Decoder.Decode_Frame (Frame, Dec);
      Put_Line ("Type=" & Integer'Image (Integer (Dec.Frame_Type_Id)));
      Put_Line ("Has pH=" & Integer'Image (Integer (Dec.Has_Ph)));
      Put_Line ("pH=" & Float'Image (Float (Dec.Ph)));
      Put_Line ("Pump-=" & Integer'Image (Integer (Dec.Pompe_Moins_Active)));
   else
      Put_Line ("Parse failed");
   end if;
end Decode_Smoke;
