with Corelec.Types;

package body Corelec.Protocol is
   use type Corelec.Types.U8;

   function CRC (Data : Corelec.Types.Frame_Array; Count : Natural) return Corelec.Types.U8 is
      C : Corelec.Types.U8 := 0;
   begin
      for I in 0 .. Integer'Min (Integer (Count) - 1, Data'Last) loop
         C := C xor Data (I);
      end loop;
      return C;
   end CRC;

   procedure Build_Ask (Cmd : Corelec.Types.U8; Packet : out Corelec.Types.Frame_Array) is
   begin
      Packet := (others => 0);
      Packet (0) := 42;
      Packet (1) := 82;
      Packet (2) := 63;
      Packet (3) := Cmd;
      Packet (4) := CRC (Packet, 4);
      Packet (5) := 42;
   end Build_Ask;

   function Parse_Frame
     (Raw       : Corelec.Types.Frame_Array;
      Out_Frame : out Corelec.Types.Frame_Type) return Boolean
   is
   begin
      Out_Frame.Frame_Type_Id := 0;
      Out_Frame.Raw := Raw;

      if Raw (0) /= 42 or else Raw (16) /= 42 then
         return False;
      end if;

      if CRC (Raw, 15) /= Raw (15) then
         return False;
      end if;

      Out_Frame.Frame_Type_Id := Raw (1);
      return True;
   end Parse_Frame;
end Corelec.Protocol;
