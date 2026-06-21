with Corelec.Types;

package Corelec.Decoder is
   pragma Preelaborate;

   procedure Decode_Frame
     (Frame : in Corelec.Types.Frame_Type;
      Out_D : out Corelec.Types.Decoded_Frame);
end Corelec.Decoder;
