with Corelec.Types;

package Corelec.Protocol is
   pragma Preelaborate;

   function CRC (Data : Corelec.Types.Frame_Array; Count : Natural) return Corelec.Types.U8;
   procedure Build_Ask (Cmd : Corelec.Types.U8; Packet : out Corelec.Types.Frame_Array);
   function Parse_Frame
     (Raw       : Corelec.Types.Frame_Array;
      Out_Frame : out Corelec.Types.Frame_Type) return Boolean;
end Corelec.Protocol;
