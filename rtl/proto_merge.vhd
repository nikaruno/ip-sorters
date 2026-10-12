library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

package typedef is

  type sorted_vector is array (NATURAL range <>) of std_logic_vector(7 downto 0);

end;


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.STD_LOGIC_unsigned.ALL;
use work.typedef.all;

-- Uncomment the following library declaration if using
-- arithmetic functions with Signed or Unsigned values
--use IEEE.NUMERIC_STD.ALL;

-- Uncomment the following library declaration if instantiating
-- any Xilinx leaf cells in this code.
--library UNISIM;
--use UNISIM.VComponents.all;

entity proto_merge is
  port ( 
    left_vector : in sorted_vector(0 to 2);
    right_vector : in sorted_vector(0 to 2);
    merged_vector : out sorted_vector(0 to 5)
  );
end proto_merge;

architecture Behavioral of proto_merge is

begin

  process(left_vector, right_vector)
    variable i : natural := 2;
    variable j : natural := 2;
  begin
    for k in 0 to 5 loop
      if(i>2) then
        merged_vector(k) <= right_vector(j);
        j := j + 1;
      elsif(j>2) then
        merged_vector(k) <= left_vector(i);
        i := i + 1;
      elsif(left_vector(i) < right_vector(j)) then
        merged_vector(k) <= left_vector(i);
        i := i + 1; 
      else
        merged_vector(k) <= right_vector(j);
        j := j + 1;
      end if;
    
    end loop;
  
  end process;


end Behavioral;
